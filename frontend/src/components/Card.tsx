import type { PropsWithChildren, ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function Card({
  title,
  actions,
  children,
  className,
}: PropsWithChildren<CardProps>) {
  return (
    <section className={`card ${className ?? ""}`}>
      {(title || actions) && (
        <header className="row" style={{ marginBottom: "0.75rem" }}>
          {title && <h3 style={{ margin: 0, fontSize: "1rem" }}>{title}</h3>}
          <div className="spacer" />
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
