"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { RUTA_TURNO } from "@/lib/api";
import { cx } from "@/lib/cx";
import { Wordmark } from "./ui/clay";
import ThemeToggle from "./theme-toggle";

export type Enlace = { href: string; label: string };

export default function NavMenu({
  enlaces,
  children,
}: {
  enlaces: Enlace[];
  children: ReactNode;
}) {
  const ruta = usePathname();
  const [abierto, setAbierto] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b-2 border-(--sw-line) bg-(--background)/90 backdrop-blur-md">
      <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center gap-x-6 px-4 sm:px-8">
        <Link href="/" className="py-3 text-xl" onClick={() => setAbierto(false)}>
          <Wordmark />
        </Link>

        <div className="ml-auto flex items-center gap-2 lg:order-last lg:ml-0">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setAbierto(!abierto)}
            aria-expanded={abierto}
            aria-controls="menu-principal"
            aria-label={abierto ? "Cerrar menu" : "Abrir menu"}
            className="clay-btn grid size-11 place-items-center rounded-full border-2 bg-(--sw-surface) text-(--sw-ink) lg:hidden"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              {abierto ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>

        <div
          id="menu-principal"
          className={cx(
            "w-full flex-col gap-4 pt-2 pb-5 lg:flex lg:w-auto lg:flex-1 lg:flex-row lg:items-center lg:justify-between lg:py-0",
            abierto ? "flex" : "hidden",
          )}
        >
          <ul className="flex flex-col lg:flex-row lg:flex-wrap lg:gap-1">
            {(ruta === RUTA_TURNO ? [] : enlaces).map((enlace) => {
              const activo = enlace.href === ruta;
              return (
                <li key={enlace.href} className="border-t border-(--sw-hairline) first:border-t-0 lg:border-0">
                  <Link
                    href={enlace.href}
                    onClick={() => setAbierto(false)}
                    aria-current={activo ? "page" : undefined}
                    className={cx(
                      "flex min-h-11 items-center px-1 text-xs font-extrabold tracking-[0.08em] uppercase transition-colors lg:rounded-full lg:px-3",
                      activo
                        ? "text-(--sw-ink) lg:bg-(--sw-accent) lg:text-(--sw-on-accent)"
                        : "text-(--sw-ink-soft) hover:text-(--sw-ink) lg:hover:bg-(--sw-bg-deep)",
                    )}
                  >
                    {enlace.label}
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="flex flex-wrap items-center gap-3">{children}</div>
        </div>
      </div>
    </header>
  );
}
