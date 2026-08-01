import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges Tailwind CSS classes with clsx and tailwind-merge.
 * This prevents class conflicts and allows for conditional styling.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}