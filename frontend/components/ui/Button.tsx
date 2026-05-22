import * as React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  isLoading?: boolean;
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-white text-black border border-white hover:bg-gray-200 disabled:hover:bg-white",
  secondary:
    "bg-[#1a1a1a] text-white border border-[#333333] hover:border-[#555555]",
  danger:
    "bg-transparent text-red-400 border border-red-900 hover:bg-red-950/50",
  ghost:
    "bg-transparent text-gray-300 border border-transparent hover:text-white hover:bg-[#1a1a1a]",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      disabled,
      isLoading = false,
      type = "button",
      variant = "primary",
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        className={cn(
          "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-[#555555] focus:ring-offset-2 focus:ring-offset-[#0a0a0a]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          variants[variant],
          className,
        )}
        {...props}
      >
        {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";
