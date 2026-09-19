import { NextRequest, NextResponse } from "next/server";

/**
 * Middleware runs on the server/edge. It can read httpOnly cookies fine
 * (httpOnly only blocks `document.cookie` access in the browser, not the
 * Cookie header a server sees) -- so it checks the real access_token
 * cookie the backend sets on login directly, no separate presence-cookie
 * workaround needed.
 *
 * This only checks that the cookie is present, not that the JWT inside it
 * is still valid -- that's still enforced API-side on every request. A
 * expired/forged cookie value passes this check and gets a real 401 from
 * the API instead, which lib/api.ts's response interceptor turns into a
 * client-side redirect. This middleware is route-level UX gating, not the
 * security boundary itself.
 */
const ACCESS_COOKIE_NAME = "access_token";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/cases",
  "/analyze",
  "/graph",
  "/risk",
  "/ai",
  "/reports",
  "/settings",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );

  if (!isProtected) {
    return NextResponse.next();
  }

  const hasAuthCookie =
    request.cookies.has(ACCESS_COOKIE_NAME) ||
    request.cookies.has("refresh_token") ||
    request.cookies.has("tracex_auth");

  if (!hasAuthCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/cases/:path*",
    "/analyze/:path*",
    "/graph/:path*",
    "/risk/:path*",
    "/ai/:path*",
    "/reports/:path*",
    "/settings/:path*",
  ],
};
