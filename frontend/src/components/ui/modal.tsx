"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/app/lib/utils";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}

const Modal = ({ isOpen, onClose, children, className }: ModalProps) => {
  // Handle Escape key to close
  React.useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden"; // Lock scroll
    }
    return () => {
      window.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "unset"; // Unlock scroll
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
      {/* Overlay */}
      <div 
        className="fixed inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" 
        onClick={onClose} 
      />
      
      {/* Modal Content */}
      <div 
        className={cn(
          "relative w-full max-w-lg transform overflow-hidden rounded-xl bg-card p-6 shadow-2xl transition-all animate-in zoom-in-95 duration-200",
          className
        )}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </button>

        {children}
      </div>
    </div>
  );
};

const ModalHeader = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("mb-4 flex flex-col space-y-1.5 text-center sm:text-left", className)}>
    {children}
  </div>
);

const ModalTitle = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <h2 className={cn("text-lg font-semibold leading-none tracking-tight", className)}>
    {children}
  </h2>
);

const ModalFooter = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <div className={cn("mt-6 flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}>
    {children}
  </div>
);

export { Modal, ModalHeader, ModalTitle, ModalFooter };