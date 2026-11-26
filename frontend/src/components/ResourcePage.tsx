import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { lazy, ReactNode, Suspense, useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage, Page } from "../lib/api";
import { useFeedback } from "./feedback";
import { Empty, ErrorBox, HelpBanner, Hint, Modal, PageHeader, Pagination, Spinner } from "./ui";

const LocationPicker = lazy(() => import("./LocationPicker"));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Row = Record<string, any>;

export interface Field {
  name: string;
  label: string; // i18n key e.g. "common:f.name"
  type: "text" | "number" | "date" | "datetime" | "select" | "checkbox" | "textarea" | "lines" | "weekdays" | "password" | "map";
  required?: boolean;
  step?: string;
  hint?: string; // i18n key shown under the field
  options?: { value: string; label: string }[];
  optionsFrom?: { resource: string; label: (r: Row) => string; params?: Record<string, string>; paramsFrom?: (v: Row) => Record<string, string> };
  dependsOn?: string; // disable until this other field has a value
  lines?: Field[];
  default?: unknown;
  createOnly?: boolean; // hidden when editing
  latKey?: string;
  lngKey?: string;
}

export interface Column { key: string; label: string; render?: (r: Row) => ReactNode; className?: string }

export interface RowAction {
  label: string;
  show?: (r: Row) => boolean;
  perm?: string;
  endpoint: (r: Row) => string;
  fields?: Field[] | ((r: Row) => Field[]);
  open?: (r: Row) => string;
  extra?: (r: Row) => Row;
  confirmText?: string;
  danger?: boolean;
}

export interface ResourceConfig {
  resource: string;
  title: string;
  help?: string; // i18n key for the "how this works" panel
  subtitle?: string;
  columns: Column[];
  fields?: Field[];
  createPerm?: string;
  createLabel?: string;
  createPath?: string;
  transform?: (values: Row) => Row;
  search?: boolean;
  filters?: { name: string; label: string; options: { value: string; label: string }[] }[];
  actions?: RowAction[];
  header?: ReactNode;
  params?: Record<string, string>;
  embedded?: boolean;
  // edit / delete
  editable?: boolean | ((r: Row) => boolean);
  editFields?: Field[] | ((r: Row) => Field[]);
  toForm?: (r: Row) => Row;
  updateTransform?: (v: Row) => Row;
  deletable?: boolean | ((r: Row) => boolean);
  deleteNeedsReason?: boolean;
  deleteLabel?: string;
  formFooter?: (values: Row, setValues: (v: Row) => void, editing: Row | null) => ReactNode;
}

function OptionsSelect({ field, value, onChange, values }: { field: Field; value: string; onChange: (v: string) => void; values: Row }) {
  const { t } = useTranslation();
  const from = field.optionsFrom;
  const params = { ...(from?.params ?? {}), ...(from?.paramsFrom?.(values) ?? {}) };
  const blocked = !!field.dependsOn && !values[field.dependsOn];
  const { data, isLoading } = useQuery({
    queryKey: ["options", from?.resource, params],
    enabled: !!from && !blocked,
    queryFn: async () => (await api.get<Page<Row>>(`/${from!.resource}/`, { params: { page_size: 200, ...params } })).data.results,
  });
  const opts = from ? (data ?? []).map((r) => ({ value: String(r.id), label: from.label(r) })) : field.options ?? [];
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)} required={field.required} disabled={blocked} aria-busy={isLoading}>
      <option value="">{blocked ? t("common:selectFirst") : t("common:select")}</option>
      {opts.map((o) => <option key={o.value} value={o.value}>{/^[a-z]+:[\w.]+$/.test(o.label) ? t(o.label) : o.label}</option>)}
    </select>
  );
}

function LinesField({ field, value, onChange, values }: { field: Field; value: Row[]; onChange: (v: Row[]) => void; values: Row }) {
  const { t } = useTranslation();
  const sub = field.lines!;
  const set = (i: number, name: string, v: unknown) => onChange(value.map((r, idx) => (idx === i ? { ...r, [name]: v } : r)));
  return (
    <div className="space-y-2">
      {value.map((row, i) => (
        <div key={i} className="grid grid-cols-[1fr_auto] items-start gap-2 rounded-xl border border-border bg-background p-2.5">
          <div className="grid gap-2 sm:grid-cols-3">
            {sub.map((f) => f.type === "select" ? (
              <OptionsSelect key={f.name} field={f} value={row[f.name] ?? ""} onChange={(v) => set(i, f.name, v)} values={values} />
            ) : (
              <input key={f.name} className="input" type="number" inputMode="decimal" step={f.step ?? "any"} min="0" placeholder={t(f.label)} aria-label={t(f.label)} value={row[f.name] ?? ""} onChange={(e) => set(i, f.name, e.target.value)} required />
            ))}
          </div>
          <button type="button" className="btn-ghost btn-sm" aria-label={t("common:actions.remove")} onClick={() => onChange(value.filter((_, idx) => idx !== i))}><Trash2 size={16} /></button>
        </div>
      ))}
      <button type="button" className="btn-outline btn-sm" onClick={() => onChange([...value, {}])}><Plus size={14} />{t("common:actions.addLine")}</button>
    </div>
  );
}

const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export function FormFields({ fields, values, setValues }: { fields: Field[]; values: Row; setValues: (v: Row) => void }) {
  const { t } = useTranslation();
  const set = (name: string, v: unknown) => setValues({ ...values, [name]: v });
  return (
    <div className="space-y-4">
      {fields.map((f) => (
        <div key={f.name} className="block text-sm">
          <label className="mb-1 block font-medium" htmlFor={`f-${f.name}`}>{t(f.label)}{f.required && <span className="text-danger"> *</span>}</label>
          {f.type === "select" ? <OptionsSelect field={f} value={values[f.name] ?? ""} onChange={(v) => set(f.name, v)} values={values} />
            : f.type === "lines" ? <LinesField field={f} value={values[f.name] ?? []} onChange={(v) => set(f.name, v)} values={values} />
            : f.type === "map" ? (
              <Suspense fallback={<div className="skeleton h-64" />}>
                <LocationPicker value={{ lat: values[f.latKey ?? "latitude"] === "" || values[f.latKey ?? "latitude"] == null ? null : Number(values[f.latKey ?? "latitude"]), lng: values[f.lngKey ?? "longitude"] === "" || values[f.lngKey ?? "longitude"] == null ? null : Number(values[f.lngKey ?? "longitude"]) }}
                  onChange={(p) => setValues({ ...values, [f.latKey ?? "latitude"]: p.lat ?? "", [f.lngKey ?? "longitude"]: p.lng ?? "" })} />
              </Suspense>
            )
            : f.type === "weekdays" ? (
              <div className="flex flex-wrap gap-2">
                {DAY_KEYS.map((d, i) => {
                  const on = (values[f.name] ?? []).includes(i);
                  return <button type="button" key={d} aria-pressed={on} className={`${on ? "btn-primary" : "btn-outline"} btn-sm`} onClick={() => set(f.name, on ? values[f.name].filter((x: number) => x !== i) : [...(values[f.name] ?? []), i])}>{t(`common:days.${d}`)}</button>;
                })}
              </div>
            )
            : f.type === "checkbox" ? <input id={`f-${f.name}`} className="h-5 w-5 accent-[rgb(var(--color-accent))]" type="checkbox" checked={!!values[f.name]} onChange={(e) => set(f.name, e.target.checked)} />
            : f.type === "textarea" ? <textarea id={`f-${f.name}`} className="input" rows={3} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} required={f.required} />
            : <input id={`f-${f.name}`} className="input" type={f.type === "datetime" ? "datetime-local" : f.type} inputMode={f.type === "number" ? "decimal" : undefined} step={f.step} value={values[f.name] ?? ""} onChange={(e) => set(f.name, e.target.value)} required={f.required} autoComplete="off" />}
          <Hint text={f.hint} />
        </div>
      ))}
    </div>
  );
}

function initialValues(fields: Field[]): Row {
  const v: Row = {};
  fields.forEach((f) => { if (f.default !== undefined) v[f.name] = f.default; else if (f.type === "lines") v[f.name] = [{}]; else if (f.type === "weekdays") v[f.name] = [0, 1, 2, 3, 4, 5, 6]; });
  return v;
}

const KEEP_EMPTY = new Set(["text", "textarea"]);
/** Drop empty optional values so they are simply not sent (edits keep empty text so it can be cleared). */
function clean(values: Row, fields: Field[], editing: boolean): Row {
  const byName = Object.fromEntries(fields.map((f) => [f.name, f]));
  const out: Row = {};
  for (const [k, v] of Object.entries(values)) {
    if (v === undefined) continue;
    if (v === "") { if (editing && KEEP_EMPTY.has(byName[k]?.type)) out[k] = ""; continue; }
    out[k] = Array.isArray(v) && v.length && typeof v[0] === "object" ? v.map((x: Row) => Object.fromEntries(Object.entries(x).filter(([, y]) => y !== ""))) : v;
  }
  return out;
}

function FormModal({ title, fields, onClose, onSubmit, initial, footer, wide }: {
  title: string; fields: Field[]; onClose: () => void; onSubmit: (v: Row) => Promise<void>; initial?: Row;
  footer?: (values: Row, setValues: (v: Row) => void) => ReactNode; wide?: boolean;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Row>({ ...initialValues(fields), ...initial });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Modal title={title} onClose={onClose} wide={wide || fields.some((f) => f.type === "map")}>
      <form onSubmit={async (e) => { e.preventDefault(); setBusy(true); setError(""); try { await onSubmit(values); onClose(); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}>
        <FormFields fields={fields} values={values} setValues={setValues} />
        {footer?.(values, setValues)}
        {error && <div className="mt-4"><ErrorBox message={error} /></div>}
        <div className="sticky bottom-0 -mx-5 mt-5 flex justify-end gap-2 border-t border-border bg-surface px-5 pb-1 pt-3">
          <button type="button" className="btn-outline" onClick={onClose}>{t("common:actions.cancel")}</button>
          <button className="btn-primary" disabled={busy}>{busy ? t("common:saving") : t("common:actions.save")}</button>
        </div>
      </form>
    </Modal>
  );
}
export { FormModal };

export default function ResourcePage({ cfg }: { cfg: ResourceConfig }) {
  const { t } = useTranslation();
  const { can } = useAuth();
  const qc = useQueryClient();
  const fb = useFeedback();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const deferred = useDeferredValue(search);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [action, setAction] = useState<{ a: RowAction; row: Row } | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);

  const params = { page, ...(deferred ? { search: deferred } : {}), ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)), ...cfg.params };
  const q = useQuery({ queryKey: [cfg.resource, params], queryFn: async () => (await api.get<Page<Row>>(`/${cfg.resource}/`, { params })).data });
  const refreshAll = () => qc.invalidateQueries();
  const canWrite = !cfg.createPerm || can(cfg.createPerm);
  const isEditable = (r: Row) => canWrite && (typeof cfg.editable === "function" ? cfg.editable(r) : !!cfg.editable);
  const isDeletable = (r: Row) => canWrite && (typeof cfg.deletable === "function" ? cfg.deletable(r) : !!cfg.deletable);
  const fieldsFor = (r: Row | null): Field[] => (r ? (typeof cfg.editFields === "function" ? cfg.editFields(r) : cfg.editFields ?? (cfg.fields ?? []).filter((f) => !f.createOnly)) : cfg.fields ?? []);

  const create = async (values: Row) => {
    const body = clean(values, cfg.fields ?? [], false);
    await api.post(cfg.createPath ?? `/${cfg.resource}/`, cfg.transform ? cfg.transform(body) : body);
    await refreshAll();
    fb.success(t("common:saved"));
  };
  const update = async (values: Row) => {
    const f = fieldsFor(editing);
    const body = clean(values, f, true);
    await api.patch(`/${cfg.resource}/${editing!.id}/`, cfg.updateTransform ? cfg.updateTransform(body) : cfg.transform ? cfg.transform(body) : body);
    await refreshAll();
    fb.success(t("common:saved"));
  };
  const remove = async (row: Row, reason?: string) => {
    await api.delete(`/${cfg.resource}/${row.id}/`, reason !== undefined ? { data: { reason } } : undefined);
    await refreshAll();
    fb.success(t("common:deleted"));
  };
  const runAction = async (a: RowAction, row: Row, values: Row = {}) => {
    await api.post(a.endpoint(row), { ...clean(values, [], false), ...(a.extra?.(row) ?? {}) });
    await refreshAll();
    fb.success(t("common:done"));
  };

  const startAction = async (a: RowAction, row: Row) => {
    if (a.open) { window.open(a.open(row), "_blank"); return; }
    if (a.fields) { setAction({ a, row }); return; }
    if (a.confirmText && !(await fb.confirm({ message: t(a.confirmText), danger: a.danger }))) return;
    try { await runAction(a, row); } catch (err) { fb.error(errorMessage(err)); }
  };
  const startDelete = async (row: Row) => {
    if (cfg.deleteNeedsReason) { setDeleting(row); return; }
    if (!(await fb.confirm({ title: t(cfg.deleteLabel ?? "common:actions.delete"), message: t("common:confirm.delete"), danger: true, confirmLabel: t(cfg.deleteLabel ?? "common:actions.delete") }))) return;
    try { await remove(row); } catch (err) { fb.error(errorMessage(err)); }
  };
  const startEdit = (row: Row) => {
    const base: Row = cfg.toForm ? cfg.toForm(row) : {};
    if (!cfg.toForm) fieldsFor(row).forEach((f) => { if (f.type === "map") { base[f.latKey ?? "latitude"] = row[f.latKey ?? "latitude"] ?? ""; base[f.lngKey ?? "longitude"] = row[f.lngKey ?? "longitude"] ?? ""; } else base[f.name] = row[f.name] ?? (f.type === "checkbox" ? false : ""); });
    setEditing({ ...row, __form: base });
  };

  const rowActions = (row: Row) => (cfg.actions ?? []).filter((a) => (!a.perm || can(a.perm)) && (!a.show || a.show(row)));
  const hasRowButtons = !!cfg.actions || !!cfg.editable || !!cfg.deletable;
  const Buttons = ({ row }: { row: Row }) => (
    <>
      {rowActions(row).map((a) => (
        <button key={a.label} className={`${a.danger ? "btn-danger" : "btn-outline"} btn-sm`} onClick={() => startAction(a, row)}>{t(a.label)}</button>
      ))}
      {isEditable(row) && <button className="btn-outline btn-sm" onClick={() => startEdit(row)} aria-label={t("common:actions.edit")}><Pencil size={14} /><span>{t("common:actions.edit")}</span></button>}
      {isDeletable(row) && <button className="btn-ghost btn-sm text-danger" onClick={() => startDelete(row)} aria-label={t(cfg.deleteLabel ?? "common:actions.delete")}><Trash2 size={14} /></button>}
    </>
  );

  const [first, ...rest] = cfg.columns;
  const emptyHint = canWrite && cfg.fields ? t("common:emptyHint") : undefined;

  return (
    <div className="space-y-4">
      {cfg.embedded ? (
        <h2 className="text-lg font-semibold">{t(cfg.title)}</h2>
      ) : (
        <PageHeader title={t(cfg.title)} subtitle={cfg.subtitle ? t(cfg.subtitle) : undefined}
          actions={cfg.fields && canWrite ? <button className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} />{t(cfg.createLabel ?? "common:actions.create")}</button> : undefined} />
      )}
      {cfg.embedded && cfg.fields && canWrite && <button className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} />{t(cfg.createLabel ?? "common:actions.create")}</button>}
      {cfg.help && <HelpBanner id={cfg.resource + (cfg.embedded ? "-e" : "")} text={cfg.help} />}
      {cfg.header}
      <div className="flex flex-wrap gap-2">
        {cfg.search !== false && (
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input className="input pl-9" placeholder={t("common:actions.search")} value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        )}
        {cfg.filters?.map((f) => (
          <select key={f.name} className="input w-auto min-w-[8rem] flex-1 sm:flex-none" value={filters[f.name] ?? ""} onChange={(e) => { setFilters({ ...filters, [f.name]: e.target.value }); setPage(1); }} aria-label={t(f.label)}>
            <option value="">{t(f.label)}</option>
            {f.options.map((o) => <option key={o.value} value={o.value}>{t(o.label, { defaultValue: o.label })}</option>)}
          </select>
        ))}
      </div>

      <div className="card overflow-hidden p-0">
        {q.isLoading ? <Spinner /> : q.isError ? <div className="p-4"><ErrorBox message={errorMessage(q.error)} /></div> : !q.data?.results.length ? <Empty hint={emptyHint} /> : (
          <>
            {/* phones: one card per record */}
            <ul className="divide-y divide-border md:hidden">
              {q.data.results.map((row) => (
                <li key={row.id} className="space-y-2 px-4 py-3.5">
                  <div className="text-[15px] font-semibold">{first.render ? first.render(row) : String(row[first.key] ?? "")}</div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-sm">
                    {rest.map((c) => (
                      <div key={c.key} className="min-w-0">
                        <dt className="text-[11px] uppercase tracking-wide text-muted">{t(c.label)}</dt>
                        <dd className="break-words">{c.render ? c.render(row) : String(row[c.key] ?? "") || "–"}</dd>
                      </div>
                    ))}
                  </dl>
                  {hasRowButtons && <div className="flex flex-wrap gap-2 pt-1"><Buttons row={row} /></div>}
                </li>
              ))}
            </ul>
            {/* tablets and desktops: table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full">
                <thead className="border-b border-border bg-secondary/60"><tr>{cfg.columns.map((c) => <th key={c.key} className="th">{t(c.label)}</th>)}{hasRowButtons && <th className="th" />}</tr></thead>
                <tbody>
                  {q.data.results.map((row) => (
                    <tr key={row.id} className="border-b border-border transition last:border-0 hover:bg-secondary/40">
                      {cfg.columns.map((c) => <td key={c.key} className={`td ${c.className ?? ""}`}>{c.render ? c.render(row) : String(row[c.key] ?? "")}</td>)}
                      {hasRowButtons && <td className="td"><div className="flex flex-wrap justify-end gap-1.5"><Buttons row={row} /></div></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {q.data && q.data.count > 0 && <Pagination page={page} count={q.data.count} onPage={setPage} />}
      </div>

      {creating && cfg.fields && <FormModal title={t(cfg.createLabel ?? "common:actions.create")} fields={cfg.fields} onClose={() => setCreating(false)} onSubmit={create} footer={cfg.formFooter ? (v, s) => cfg.formFooter!(v, s, null) : undefined} />}
      {editing && <FormModal title={t("common:actions.edit")} fields={fieldsFor(editing)} initial={editing.__form} onClose={() => setEditing(null)} onSubmit={update} footer={cfg.formFooter ? (v, s) => cfg.formFooter!(v, s, editing) : undefined} />}
      {action && <FormModal title={t(action.a.label)} fields={typeof action.a.fields === "function" ? action.a.fields(action.row) : action.a.fields!} onClose={() => setAction(null)} onSubmit={(v) => runAction(action.a, action.row, v)} />}
      {deleting && <FormModal title={t(cfg.deleteLabel ?? "common:actions.delete")} fields={[{ name: "reason", label: "common:f.reason", type: "text", required: true, hint: "hints:field.reason" }]} onClose={() => setDeleting(null)} onSubmit={(v) => remove(deleting, v.reason)} />}
    </div>
  );
}
