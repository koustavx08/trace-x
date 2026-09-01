// Mock axios before importing the module under test so that the ApiClient
// constructor (which calls axios.create) receives the mocked instance. The
// instance is created inside the factory (jest.mock factories are hoisted
// above regular const declarations, so it can't safely reference an
// outer-scope variable) and re-exposed as `__mockInstance` for the tests.
jest.mock("axios", () => {
  const instance = {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  return {
    __esModule: true,
    default: { create: jest.fn(() => instance) },
    __mockInstance: instance,
  };
});

import {
  api,
  casesApi,
  walletsApi,
  healthApi,
  graphApi,
  reportsApi,
} from "./api";

const mockAxios = jest.requireMock("axios") as { default: { create: jest.Mock }; __mockInstance: any };
const mockAxiosInstance = mockAxios.__mockInstance as {
  get: jest.Mock;
  post: jest.Mock;
  patch: jest.Mock;
  delete: jest.Mock;
  interceptors: { request: { use: jest.Mock }; response: { use: jest.Mock } };
};

describe("ApiClient construction", () => {
  it("creates an axios instance with the expected base config", () => {
    expect(mockAxios.default.create).toHaveBeenCalledWith(
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
        timeout: 30000,
        // Access/refresh tokens live in httpOnly cookies the backend sets;
        // this is what actually attaches them to requests -- there's no
        // request interceptor injecting an Authorization header anymore
        // because there's no token in JS-reachable state to inject.
        withCredentials: true,
      })
    );
  });

  it("registers a response interceptor", () => {
    expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalled();
  });
});

describe("ApiClient http methods", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("get() unwraps response.data and forwards params", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { ok: true } });
    const result = await api.get("/foo", { a: 1 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/foo", { params: { a: 1 } });
    expect(result).toEqual({ ok: true });
  });

  it("post() unwraps response.data and forwards the body", async () => {
    mockAxiosInstance.post.mockResolvedValueOnce({ data: { id: "1" } });
    const result = await api.post("/foo", { name: "bar" });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith("/foo", { name: "bar" }, { params: undefined });
    expect(result).toEqual({ id: "1" });
  });

  it("patch() unwraps response.data", async () => {
    mockAxiosInstance.patch.mockResolvedValueOnce({ data: { updated: true } });
    const result = await api.patch("/foo/1", { name: "baz" });
    expect(mockAxiosInstance.patch).toHaveBeenCalledWith("/foo/1", { name: "baz" });
    expect(result).toEqual({ updated: true });
  });

  it("delete() unwraps response.data", async () => {
    mockAxiosInstance.delete.mockResolvedValueOnce({ data: null });
    const result = await api.delete("/foo/1");
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith("/foo/1");
    expect(result).toBeNull();
  });

  it("propagates rejected requests", async () => {
    mockAxiosInstance.get.mockRejectedValueOnce(new Error("network error"));
    await expect(api.get("/fail")).rejects.toThrow("network error");
  });
});

describe("resource API helpers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("casesApi.list calls GET /cases with params", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });
    await casesApi.list({ page: 1, page_size: 10 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/cases", { params: { page: 1, page_size: 10 } });
  });

  it("casesApi.get calls GET /cases/:id", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { id: "c1" } });
    await casesApi.get("c1");
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/cases/c1", { params: undefined });
  });

  it("casesApi.create calls POST /cases with the payload", async () => {
    mockAxiosInstance.post.mockResolvedValueOnce({ data: { id: "c1" } });
    await casesApi.create({ title: "New case" });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith("/cases", { title: "New case" }, { params: undefined });
  });

  it("walletsApi.list calls GET /wallets with params", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });
    await walletsApi.list({ case_id: "c1" });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/wallets", { params: { case_id: "c1" } });
  });

  it("healthApi.check calls GET /health", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { status: "healthy" } });
    const result = await healthApi.check();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/health", { params: undefined });
    expect(result).toEqual({ status: "healthy" });
  });

  it("graphApi.getSubgraph calls POST /graph/subgraph with the request body", async () => {
    mockAxiosInstance.post.mockResolvedValueOnce({ data: { nodes: [], edges: [] } });
    await graphApi.getSubgraph({ addresses: ["0xabc"], chain: "ethereum" });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      "/graph/subgraph",
      {
        addresses: ["0xabc"],
        chain: "ethereum",
      },
      { params: undefined }
    );
  });

  it("reportsApi.list calls GET /reports with params", async () => {
    mockAxiosInstance.get.mockResolvedValueOnce({ data: { items: [], total: 0 } });
    await reportsApi.list({ case_id: "c1" });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith("/reports", { params: { case_id: "c1" } });
  });
});
