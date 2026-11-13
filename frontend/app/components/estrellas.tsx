/** "★★★★☆" con su lectura para lectores de pantalla; el numero no depende solo del color. */
export function Estrellas({ estrellas, className = "" }: { estrellas: number; className?: string }) {
  return (
    <span role="img" aria-label={`${estrellas} de 5 estrellas`} className={`tracking-wider text-(--sw-ink) ${className}`}>
      {"★".repeat(estrellas)}
      <span className="text-(--sw-ink-soft)">{"☆".repeat(5 - estrellas)}</span>
    </span>
  );
}
