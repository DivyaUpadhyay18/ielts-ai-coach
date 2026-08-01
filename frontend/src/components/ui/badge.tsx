import * as React from "react";
import { cn } from "@/app/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning' | 'accent';
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80",
    secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
    destructive: "border-transparent bg-error text-white shadow hover:bg-error/80",
    outline: "text-foreground border-border",
    success: "border-transparent bg-success text-white shadow hover:bg-success/80",
    warning: "border-transparent bg-warning text-white shadow hover:bg-warning/80",
    accent: "border-transparent bg-accent text-accent-foreground shadow hover:bg-accent/80",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };