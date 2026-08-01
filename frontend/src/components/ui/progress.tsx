import * as React from "react";
import { cn } from "@/app/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number; // 0 to 100
  indicatorClassName?: string;
  variant?: 'default' | 'success' | 'warning' | 'accent';
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, indicatorClassName, variant = 'default', ...props }, ref) => {
    
    const variants = {
      default: "bg-primary",
      success: "bg-success",
      warning: "bg-warning",
      accent: "bg-accent",
    };

    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        className={cn(
          "relative h-4 w-full overflow-hidden rounded-full bg-secondary",
          className
        )}
        {...props}
      >
        <div
          className={cn(
            "h-full w-full flex-1 transition-all duration-500 ease-in-out",
            variants[variant],
            indicatorClassName
          )}
          style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
      </div>
    );
  }
);

Progress.displayName = "Progress";

export { Progress };