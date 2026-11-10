import { NextResponse, type NextRequest } from "next/server";

// Visitors without a session land on the welcome page. Signed-in users keep "/" as their home.
export function middleware(req: NextRequest) {
  if (!req.cookies.has("medora_token")) {
    return NextResponse.redirect(new URL("/welcome", req.url));
  }
  return NextResponse.next();
}

export const config = { matcher: "/" };
