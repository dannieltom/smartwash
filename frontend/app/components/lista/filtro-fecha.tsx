import { ClayField, ClaySelect } from "../ui/clay";
import { diasDelMes, MESES } from "./url";

type Fecha = { anio: string; mes: string; dia: string };

/** Ano, mes y dia encadenados: el mes se habilita con el ano y el dia con el mes; cambiar uno
 * reinicia los que dependen de el. */
export default function FiltroFecha({
  anio,
  mes,
  dia,
  anios,
  onCambiar,
}: Fecha & { anios: number[]; onCambiar: (cambios: Fecha) => void }) {
  const opcionesAnio = [...new Set([...anios, ...(anio ? [Number(anio)] : [])])].sort((a, b) => b - a);
  const dias = anio && mes ? diasDelMes(anio, mes) : 0;

  return (
    <>
      <ClayField label="Año">
        <ClaySelect value={anio} onChange={(e) => onCambiar({ anio: e.target.value, mes: "", dia: "" })}>
          <option value="">Todos</option>
          {opcionesAnio.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </ClaySelect>
      </ClayField>
      <ClayField label="Mes">
        <ClaySelect value={mes} disabled={!anio} onChange={(e) => onCambiar({ anio, mes: e.target.value, dia: "" })}>
          <option value="">Todos</option>
          {MESES.map((nombre, i) => (
            <option key={nombre} value={i + 1}>
              {nombre}
            </option>
          ))}
        </ClaySelect>
      </ClayField>
      <ClayField label="Día">
        <ClaySelect value={dia} disabled={!mes} onChange={(e) => onCambiar({ anio, mes, dia: e.target.value })}>
          <option value="">Todos</option>
          {Array.from({ length: dias }, (_, i) => i + 1).map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </ClaySelect>
      </ClayField>
    </>
  );
}
