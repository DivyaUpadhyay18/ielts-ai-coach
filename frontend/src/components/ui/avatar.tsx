"use client";

import * as React from "react";
import Image from "next/image";
import { User } from "lucide-react";
import { cn } from "@/app/lib/utils";

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string | null;
  alt?: string;
  fallback?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, src, alt, fallback, size = 'md', ...props }, ref) => {
    const [hasError, setHasError] = React.useState(false);

    const sizes = {
      sm: "h-8 w-8 text-xs",
      md: "h-10 w-10 text-sm",
      lg: "h-16 w-16 text-xl",
      xl: "h-24 w-24 text-2xl",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex shrink-0 overflow-hidden rounded-full bg-secondary",
          sizes[size],
          className
        )}
        {...props}
      >
        {src && !hasError ? (
          <Image
            src={src}
            alt={alt || "User avatar"}
            fill
            sizes="(max-width: 768px) 100vw, 256px"
            className="object-cover"
            onError={() => setHasError(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center font-medium uppercase text-muted-foreground">
            {fallback ? (
              fallback.substring(0, 2)
            ) : (
              <User className="h-1/2 w-1/2" />
            )}
          </div>
        )}
      </div>
    );
  }
);

Avatar.displayName = "Avatar";

export { Avatar };
