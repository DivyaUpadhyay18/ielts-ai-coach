import React from "react";
import { Navbar } from "@/components/shared/navbar";
import { Footer } from "@/components/shared/footer";

interface LandingLayoutProps {
  children: React.ReactNode;
}

const LandingLayout = ({ children }: LandingLayoutProps) => {
  return (
    <div className="relative flex min-h-screen flex-col">
      {/* The Navbar stays at the top of every public page */}
      <Navbar />
      
      {/* 
        The main tag grows to fill all available space (flex-1).
        This ensures that even if a page has very little content,
        the footer stays at the bottom of the screen.
      */}
      <main className="flex-1">
        {children}
      </main>

      {/* The Footer stays at the bottom of every public page */}
      <Footer />
    </div>
  );
};

export { LandingLayout };