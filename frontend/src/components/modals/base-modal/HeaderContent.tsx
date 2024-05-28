import React from "react";

interface HeaderContentProps {
  title: string;
  subtitle?: string;
}

export function HeaderContent({ title, subtitle = undefined }: HeaderContentProps) {
  return (
    <>
      <h3>{title}</h3>
      {subtitle && (
        <span className="text-neutral-400 text-sm font-light">{subtitle}</span>
      )}
    </>
  );
}
