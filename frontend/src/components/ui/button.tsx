import * as React from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/app/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link' | 'accent' | 'success';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  isLoading?: boolean;
  leftIcon?: LucideIcon;
  rightIcon?: LucideIcon;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", isLoading, leftIcon: LeftIcon, rightIcon: RightIcon, children, disabled, ...props }, ref) => {
    
    // Base styles + variants mapping
    const variants = {
      default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow",
      destructive: "bg-error text-white hover:bg-error/90 shadow-sm",
      outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
      secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
      ghost: "hover:bg-accent hover:text-accent-foreground",
      link: "text-primary underline-offset-4 hover:underline",
      accent: "bg-accent text-accent-foreground hover:bg-accent/90 shadow",
      success: "bg-success text-white hover:bg-success/90 shadow",
    };

    const sizes = {
      default: "h-10 px-4 py-2",
      sm: "h-9 rounded-md px-3 text-xs",
      lg: "h-11 rounded-md px-8 text-base",
      icon: "h-10 w-10",
    };

    return (
      <button
        ref={ref}
        disabled={isLoading || disabled}
        className={cn(
          "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-95",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {isLoading && (
          <svg className="mr-2 h-4 w-4 animate-spin text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        )}
        {!isLoading && LeftIcon && <LeftIcon className="mr-2 h-4 w-4" />}
        {children}
        {!isLoading && RightIcon && <RightIcon className="ml-2 h-4 w-4" />}
      </button>
    );
  }
);

Button.displayName = "Button";

export { Button };