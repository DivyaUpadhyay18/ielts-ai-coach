import * as React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/app/lib/utils";

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'primary' | 'secondary' | 'white' | 'accent';
}

const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ className, size = 'md', variant = 'primary', ...props }, ref) => {
    
    const sizes = {
      sm: "h-4 w-4 stroke-[3px]",
      md: "h-6 w-6 stroke-[2px]",
      lg: "h-8 w-8 stroke-[2px]",
      xl: "h-12 w-12 stroke-[1.5px]",
    };

    const variants = {
      primary: "text-primary",
      secondary: "text-muted-foreground",
      white: "text-white",
      accent: "text-accent",
    };

    return (
      <div
        ref={ref}
        role="status"
        aria-label="Loading"
        className={cn("flex items-center justify-center", className)}
        {...props}
      >
        <Loader2 
          className={cn(
            "animate-spin", 
            sizes[size], 
            variants[variant]
          )} 
        />
        <span className="sr-only">Loading...</span>
      </div>
    );
  }
);

Spinner.displayName = "Spinner";

export { Spinner };