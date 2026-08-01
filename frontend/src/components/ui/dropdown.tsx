"use client";

import * as React from "react";
import { cn } from "@/app/lib/utils";

interface DropdownContextProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
}

const DropdownContext = React.createContext<DropdownContextProps | undefined>(undefined);

const Dropdown = ({ children, className }: { children: React.ReactNode; className?: string }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Close when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <DropdownContext.Provider value={{ isOpen, setIsOpen }}>
      <div ref={containerRef} className={cn("relative inline-block text-left", className)}>
        {children}
      </div>
    </DropdownContext.Provider>
  );
};

const DropdownTrigger = ({ children }: { children: React.ReactNode }) => {
  const context = React.useContext(DropdownContext);
  if (!context) throw new Error("DropdownTrigger must be used within Dropdown");
  return (
    <div onClick={() => context.setIsOpen(!context.isOpen)} className="cursor-pointer">
      {children}
    </div>
  );
};

const DropdownMenu = ({ 
  children, 
  align = "right", 
  className 
}: { 
  children: React.ReactNode; 
  align?: "left" | "right"; 
  className?: string 
}) => {
  const context = React.useContext(DropdownContext);
  if (!context) throw new Error("DropdownMenu must be used within Dropdown");

  if (!context.isOpen) return null;

  return (
    <div
      className={cn(
        "absolute mt-2 w-56 rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50 animate-fade-in",
        align === "right" ? "right-0" : "left-0",
        className
      )}
    >
      {children}
    </div>
  );
};

const DropdownItem = ({ 
  children, 
  onClick, 
  className,
  variant = "default"
}: { 
  children: React.ReactNode; 
  onClick?: () => void; 
  className?: string;
  variant?: "default" | "destructive";
}) => {
  const context = React.useContext(DropdownContext);
  if (!context) throw new Error("DropdownItem must be used within Dropdown");

  const handleClick = () => {
    if (onClick) onClick();
    context.setIsOpen(false);
  };

  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex w-full items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50",
        variant === "destructive" && "text-error hover:bg-error/10 hover:text-error",
        className
      )}
    >
      {children}
    </button>
  );
};

export { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem };