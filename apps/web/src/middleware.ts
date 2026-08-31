import { NextRequest, NextResponse } from "next/server";

/**
 * Middleware runs on the server/edge and has no access to localStorage,
 * where the real access/refresh tokens live (see store/auth-store.ts).
 * As a pragmatic middle ground, auth-store also sets a lightweight,
 * non-httpOnly "tracex_auth" presence cookie on login/logout/rehydrate.
 * This middleware only checks for that cookie's presence - it does NOT
 * validate the JWT itself (that still happens API-side on every request).
 * A client can forge this cookie to bypass the redirect, but they still
 * cannot call any protected API route without a valid Bearer token, so
 * this is route-level UX gating, not a security boundary by itself.
 */
const AUTH_COOKIE_NAME = "tracex_auth";

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

  const hasAuthCookie = request.cookies.has(AUTH_COOKIE_NAME);

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
