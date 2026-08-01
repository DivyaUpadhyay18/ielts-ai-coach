"use client";

import * as React from "react";
import { cn } from "@/app/lib/utils";

interface TabsContextProps {
  activeValue: string;
  setActiveValue: (value: string) => void;
}

const TabsContext = React.createContext<TabsContextProps | undefined>(undefined);

const Tabs = ({ 
  defaultValue, 
  children, 
  className 
}: { 
  defaultValue: string; 
  children: React.ReactNode; 
  className?: string 
}) => {
  const [activeValue, setActiveValue] = React.useState(defaultValue);

  return (
    <TabsContext.Provider value={{ activeValue, setActiveValue }}>
      <div className={cn("w-full", className)}>{children}</div>
    </TabsContext.Provider>
  );
};

const TabsList = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
      className
    )}
    {...props}
  />
);

const TabsTrigger = ({ 
  value, 
  className, 
  children, 
  ...props 
}: { 
  value: string; 
  className?: string; 
  children: React.ReactNode 
} & React.ButtonHTMLAttributes<HTMLButtonElement>) => {
  const context = React.useContext(TabsContext);
  if (!context) throw new Error("TabsTrigger must be used within Tabs");

  const isActive = context.activeValue === value;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={() => context.setActiveValue(value)}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        isActive 
          ? "bg-background text-foreground shadow-sm" 
          : "hover:bg-background/50 hover:text-foreground",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
};

const TabsContent = ({ 
  value, 
  className, 
  children, 
  ...props 
}: { 
  value: string; 
  className?: string; 
  children: React.ReactNode 
} & React.HTMLAttributes<HTMLDivElement>) => {
  const context = React.useContext(TabsContext);
  if (!context) throw new Error("TabsContent must be used within Tabs");

  if (context.activeValue !== value) return null;

  return (
    <div
      role="tabpanel"
      className={cn(
        "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 animate-fade-in",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export { Tabs, TabsList, TabsTrigger, TabsContent };