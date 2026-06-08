import { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

export function Field({ label, className = "", ...props }: FieldProps) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-700">
      {label}
      <input className={`rounded border border-stone-300 bg-white px-3 py-2 outline-none focus:border-accent ${className}`} {...props} />
    </label>
  );
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
};

export function Textarea({ label, className = "", ...props }: TextareaProps) {
  return (
    <label className="grid gap-2 text-sm font-medium text-stone-700">
      {label}
      <textarea
        className={`min-h-28 rounded border border-stone-300 bg-white px-3 py-2 outline-none focus:border-accent ${className}`}
        {...props}
      />
    </label>
  );
}
