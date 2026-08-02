import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Protected routes that require authentication
const protectedRoutes = [
  '/dashboard',
  '/writing',
  '/speaking',
  '/roadmap',
  '/analytics',
  '/diagnostic',
  '/notifications',
  '/profile',
  '/settings',
  '/resources',
];

// Auth routes (redirect to dashboard if already authenticated)
const authRoutes = [
  '/login',
  '/signup',
  '/forgot-password',
];

// Check if a route is protected
const isProtectedRoute = (path: string): boolean => {
  return protectedRoutes.some(route => path.startsWith(route));
};

// Check if a route is an auth route
const isAuthRoute = (path: string): boolean => {
  return authRoutes.some(route => path.startsWith(route));
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Get the token from the cookie
  const accessToken = request.cookies.get('ielts_access_token')?.value;
  const isAuthenticated = !!accessToken;

  // Redirect to login if accessing protected route without auth
  if (isProtectedRoute(pathname) && !isAuthenticated) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect to dashboard if accessing auth routes while authenticated
  if (isAuthRoute(pathname) && isAuthenticated) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|images|api).*)',
  ],
};
