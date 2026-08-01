"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, X, BookOpen, BarChart3, MessageSquare, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { 
  Dropdown, 
  DropdownTrigger, 
  DropdownMenu, 
  DropdownItem 
} from "@/components/ui/dropdown";
import { useAuthStore } from "@/app/store/useAuthStore";

const Navbar = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
  const router = useRouter();
  const { user } = useAuthStore();

  const navLinks = [
    { name: "Writing", href: "/writing", icon: BookOpen },
    { name: "Speaking", href: "/speaking", icon: MessageSquare },
    { name: "Progress", href: "/analytics", icon: BarChart3 },
  ];

  return (
    <nav className="sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur-md">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        
        {/* Logo Area */}
        <Link href="/" className="flex items-center space-x-2 transition-opacity hover:opacity-90">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Zap className="h-5 w-5 fill-current" />
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">
            IELTS<span className="text-accent">AI</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex md:items-center md:space-x-6">
          {navLinks.map((link) => (
            <Link
              key={link.name}
              href={link.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              {link.name}
            </Link>
          ))}
        </div>

        {/* Action Area (Desktop) */}
        <div className="hidden md:flex md:items-center md:space-x-4">
          {user ? (
            <Dropdown>
              <DropdownTrigger>
                <Avatar 
                  size="sm" 
                  fallback={user.full_name || "U"} 
                  className="cursor-pointer ring-2 ring-transparent transition-all hover:ring-primary/50" 
                />
              </DropdownTrigger>
              <DropdownMenu align="right">
                <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">My Account</div>
                <DropdownItem onClick={() => router.push('/dashboard')}>Dashboard</DropdownItem>
                <DropdownItem onClick={() => router.push('/settings')}>Settings</DropdownItem>
                <hr className="my-1 border-border" />
                <DropdownItem variant="destructive" onClick={() => { useAuthStore.getState().logout(); router.push('/'); }}>Logout</DropdownItem>
              </DropdownMenu>
            </Dropdown>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost" size="sm">Login</Button>
              </Link>
              <Link href="/signup">
                <Button size="sm">Get Started</Button>
              </Link>
            </>
          )}
        </div>

        {/* Mobile Toggle */}
        <button
          className="flex items-center justify-center rounded-md p-2 text-muted-foreground md:hidden"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        >
          {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="border-b border-border bg-background p-4 md:hidden animate-fade-in">
          <div className="flex flex-col space-y-4">
            {navLinks.map((link) => (
              <Link
                key={link.name}
                href={link.href}
                className="flex items-center space-x-2 text-base font-medium text-foreground"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                <link.icon className="h-5 w-5 text-muted-foreground" />
                <span>{link.name}</span>
              </Link>
            ))}
            <hr className="border-border" />
            {!user ? (
              <div className="flex flex-col space-y-2">
                <Button variant="outline" className="w-full">Login</Button>
                <Button className="w-full">Get Started</Button>
              </div>
            ) : (
              <Button variant="ghost" className="justify-start px-0">Logout</Button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export { Navbar };