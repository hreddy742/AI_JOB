import { NextRequest, NextResponse } from "next/server";

const publicRoutes = [
  "/",
  "/auth/login",
  "/auth/register",
  "/auth/verify-email",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/callback",
  "/auth/resend-verification",
  "/login",
  "/register",
];

const protectedPrefixes = ["/dashboard", "/jobs", "/applications", "/profile", "/settings", "/copilot", "/resumes", "/outreach", "/referrals", "/analytics"];

export function middleware(request: NextRequest): NextResponse {
  const path = request.nextUrl.pathname;
  const hasRefresh = Boolean(request.cookies.get("apex_refresh_token")?.value);

  const isPublic = publicRoutes.some((route) => path === route || path.startsWith(`${route}/`));
  const isProtected = protectedPrefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));

  if (isProtected && !hasRefresh) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/login";
    url.searchParams.set("redirect", path);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
