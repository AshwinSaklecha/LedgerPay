import * as React from "react";
import { cn } from "@/lib/utils";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, hint, id, label, ...props }, ref) => {
    const inputId = id ?? label.toLowerCase().replace(/\s+/g, "-");

    return (
      <label className="grid gap-2 text-sm text-gray-300" htmlFor={inputId}>
        <span className="font-medium text-gray-200">{label}</span>
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "h-11 rounded-lg border border-[#333333] bg-[#161616] px-3 text-sm text-white outline-none transition-colors",
            "placeholder:text-gray-600 focus:border-[#555555] focus:ring-2 focus:ring-[#555555]/40",
            className,
          )}
          {...props}
        />
        {hint ? <span className="text-xs text-gray-500">{hint}</span> : null}
      </label>
    );
  },
);

Input.displayName = "Input";
