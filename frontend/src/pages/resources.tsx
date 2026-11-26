import { FeeQuote, QuickAddress, RecipeRequirements } from "../components/formWidgets";
import { Badge } from "../components/ui";
import type { Field, ResourceConfig, Row } from "../components/ResourcePage";
import { dateOnly, dateTime, money, num } from "../lib/format";

const yes = (v: boolean) => (v ? "✓" : "–");
const status = (key: string) => (r: Row) => <Badge value={r[key]} />;
const opt = (...values: string[]) => values.map((v) => ({ value: v, label: `common:status.${v}` }));
const methods = [{ value: "cash", label: "orders:method.cash" }, { value: "upi", label: "orders:method.upi" }, { value: "bank", label: "orders:method.bank" }];
const groups = [{ value: "household", label: "masters:group.household" }, { value: "hotel", label: "masters:group.hotel" }, { value: "bulk", label: "masters:group.bulk" }];
const location = (extra: Partial<Field> = {}): Field => ({ name: "location", label: "common:f.location", type: "select", required: true, optionsFrom: { resource: "locations", label: (r) => r.name }, ...extra });
const packageSel = (name = "package"): Field => ({ name, label: "common:f.package", type: "select", optionsFrom: { resource: "packages", label: (r) => `${r.product_name} ${r.name}` } });
const lineFields = (): Field[] => [packageSel(), { name: "quantity", label: "common:f.quantity", type: "number", step: "1" }];
const toLines = (v: Row) => ({ ...v, lines: (v.lines ?? []).map((l: Row) => ({ package: l.package, quantity: Number(l.quantity) })) });
const reasonField: Field = { name: "reason", label: "common:f.reason", type: "text", required: true, hint: "hints:field.reason" };

/* ------------------------------ SALES ------------------------------ */
const orderFields: Field[] = [
  { name: "customer", label: "common:f.customer", type: "select", required: true, createOnly: true, hint: "hints:field.orderCustomer", optionsFrom: { resource: "customers", label: (r) => `${r.name} (${r.phone})` } },
  location({ createOnly: true }),
  { name: "lines", label: "orders:f.items", type: "lines", hint: "hints:field.orderLines", lines: lineFields() },
  { name: "delivery_address", label: "orders:f.address", type: "select", required: true, dependsOn: "customer", hint: "hints:field.orderAddress", optionsFrom: { resource: "customer-addresses", label: (r) => `${r.label}: ${r.address_line}`, paramsFrom: (v) => ({ customer: v.customer }) } },
  { name: "scheduled_date", label: "orders:f.scheduled", type: "date", hint: "hints:field.scheduled" },
  { name: "coupon_code", label: "orders:f.coupon", type: "text", createOnly: true, hint: "hints:field.coupon" },
  { name: "delivery_instructions", label: "orders:f.instructions", type: "textarea", hint: "hints:field.instructions" },
];

export const orders: ResourceConfig = {
  resource: "orders", title: "common:nav.orders", help: "hints:page.orders", createPerm: "orders.create", createLabel: "orders:new",
  columns: [
    { key: "order_number", label: "orders:f.number" }, { key: "customer_name", label: "common:f.customer" },
    { key: "scheduled_date", label: "orders:f.scheduled", render: (r) => dateOnly(r.scheduled_date) },
    { key: "delivery_fee", label: "orders:f.deliveryFee", render: (r) => (Number(r.delivery_fee) ? money(r.delivery_fee) : "Free"), className: "text-right" },
    { key: "total", label: "common:f.total", render: (r) => money(r.total), className: "text-right" },
    { key: "status", label: "common:f.status", render: status("status") },
    { key: "payment_status", label: "orders:f.payment", render: status("payment_status") },
  ],
  filters: [{ name: "status", label: "common:f.status", options: opt("pending", "confirmed", "dispatched", "completed", "cancelled") }],
  fields: orderFields,
  transform: toLines,
  editable: (r) => ["pending", "confirmed"].includes(r.status),
  editFields: (r) => (r.status === "pending" ? orderFields.filter((f) => !f.createOnly) : [orderFields[6]]),
  toForm: (r) => ({ lines: r.lines.map((l: Row) => ({ package: l.package, quantity: String(l.quantity) })), delivery_address: r.delivery_address ?? "", scheduled_date: r.scheduled_date, delivery_instructions: r.delivery_instructions, customer: r.customer, location: r.location }),
  updateTransform: (v) => (v.lines ? toLines(v) : v),
  formFooter: (v, s, editing) => (<><QuickAddress values={{ ...v, customer: v.customer || editing?.customer }} setValues={s} /><FeeQuote values={{ ...v, location: v.location || editing?.location }} /></>),
  actions: [
    { label: "orders:act.confirm", perm: "orders.confirm", show: (r) => r.status === "pending", endpoint: (r) => `/orders/${r.id}/confirm/`, confirmText: "hints:confirm.orderConfirm" },
    { label: "orders:act.dispatch", perm: "orders.dispatch", show: (r) => r.status === "confirmed", endpoint: (r) => `/orders/${r.id}/dispatch/`, confirmText: "hints:confirm.orderDispatch" },
    { label: "orders:act.complete", perm: "orders.dispatch", show: (r) => r.status === "dispatched", endpoint: (r) => `/orders/${r.id}/complete/` },
    { label: "orders:act.cancel", perm: "orders.cancel", danger: true, show: (r) => ["pending", "confirmed"].includes(r.status), endpoint: (r) => `/orders/${r.id}/cancel/`, fields: [reasonField] },
  ],
};

export const invoices: ResourceConfig = {
  resource: "invoices", title: "common:nav.invoices", help: "hints:page.invoices",
  columns: [
    { key: "invoice_number", label: "orders:f.invoice" }, { key: "customer_name", label: "common:f.customer" },
    { key: "issued_at", label: "common:f.date", render: (r) => dateTime(r.issued_at) },
    { key: "invoice_type", label: "common:f.type", render: (r) => <Badge value={r.invoice_type} /> },
    { key: "total", label: "common:f.total", render: (r) => money(r.total), className: "text-right" },
    { key: "paid", label: "orders:f.paid", render: (r) => money(r.paid), className: "text-right" },
    { key: "outstanding", label: "orders:f.outstanding", render: (r) => money(r.outstanding), className: "text-right" },
  ],
  actions: [
    { label: "orders:act.pay", perm: "payments.record", show: (r) => Number(r.outstanding) > 0, endpoint: () => "/payments/record/", extra: (r) => ({ invoice: r.id }),
      fields: (r) => [
        { name: "method", label: "orders:f.method", type: "select", required: true, default: "cash", options: methods, hint: "hints:field.method" },
        { name: "amount", label: "common:f.amount", type: "number", step: "0.01", required: true, default: r.outstanding, hint: "hints:field.payAmount" },
        { name: "tender_amount", label: "orders:f.tender", type: "number", step: "0.01", hint: "hints:field.tender" },
        { name: "reference", label: "orders:f.reference", type: "text", hint: "hints:field.reference" },
      ] },
    { label: "common:actions.print", endpoint: () => "", open: (r) => `/api/v1/invoices/${r.id}/print/` },
  ],
};

export const cashClosings: ResourceConfig = {
  resource: "cash-closings", title: "common:nav.cashClosing", help: "hints:page.cashClosing", createPerm: "cash.close", search: false,
  columns: [
    { key: "date", label: "common:f.date", render: (r) => dateOnly(r.date) },
    { key: "expected_cash", label: "orders:f.expectedCash", render: (r) => money(r.expected_cash), className: "text-right" },
    { key: "counted_cash", label: "orders:f.countedCash", render: (r) => money(r.counted_cash), className: "text-right" },
    { key: "difference", label: "orders:f.difference", render: (r) => <span className={Number(r.difference) < 0 ? "text-danger" : ""}>{money(r.difference)}</span>, className: "text-right" },
  ],
  fields: [location(), { name: "date", label: "common:f.date", type: "date", required: true }, { name: "counted_cash", label: "orders:f.countedCash", type: "number", step: "0.01", required: true, hint: "hints:field.countedCash" }, { name: "notes", label: "common:f.notes", type: "text" }],
};

const subFields: Field[] = [
  { name: "customer", label: "common:f.customer", type: "select", required: true, createOnly: true, optionsFrom: { resource: "customers", label: (r) => r.name } },
  location(),
  { name: "delivery_address", label: "orders:f.address", type: "select", required: true, dependsOn: "customer", hint: "hints:field.orderAddress", optionsFrom: { resource: "customer-addresses", label: (r) => `${r.label}: ${r.address_line}`, paramsFrom: (v) => ({ customer: v.customer }) } },
  { name: "plan_type", label: "orders:f.plan", type: "select", required: true, default: "monthly", options: [{ value: "weekly", label: "orders:plan.weekly" }, { value: "monthly", label: "orders:plan.monthly" }, { value: "annual", label: "orders:plan.annual" }] },
  { name: "start_date", label: "orders:f.start", type: "date", required: true },
  { name: "end_date", label: "orders:f.end", type: "date", hint: "hints:field.subEnd" },
  { name: "delivery_weekdays", label: "orders:f.days", type: "weekdays", hint: "hints:field.planDays" },
  { name: "lines", label: "orders:f.items", type: "lines", lines: lineFields() },
];
export const subscriptions: ResourceConfig = {
  resource: "subscriptions", title: "common:nav.subscriptions", help: "hints:page.subscriptions", createPerm: "subscriptions.manage",
  columns: [
    { key: "customer_name", label: "common:f.customer" }, { key: "plan_type", label: "orders:f.plan" },
    { key: "start_date", label: "orders:f.start", render: (r) => dateOnly(r.start_date) }, { key: "end_date", label: "orders:f.end", render: (r) => dateOnly(r.end_date) },
    { key: "status", label: "common:f.status", render: status("status") },
  ],
  fields: subFields, transform: toLines,
  editable: (r) => ["active", "paused"].includes(r.status),
  toForm: (r) => ({ customer: r.customer, location: r.location, delivery_address: r.delivery_address ?? "", plan_type: r.plan_type, start_date: r.start_date, end_date: r.end_date, delivery_weekdays: r.delivery_weekdays, lines: r.lines.map((l: Row) => ({ package: l.package, quantity: String(l.quantity) })) }),
  actions: ["pause", "resume", "cancel", "renew"].map((a) => ({
    label: `orders:act.${a}`, perm: "subscriptions.manage", danger: a === "cancel", confirmText: a === "cancel" ? "hints:confirm.subCancel" : undefined,
    show: (r: Row) => (a === "pause" ? r.status === "active" : a === "resume" ? r.status === "paused" : a === "cancel" ? ["active", "paused"].includes(r.status) : ["expired", "active", "cancelled"].includes(r.status)),
    endpoint: (r: Row) => `/subscriptions/${r.id}/${a}/`,
  })),
};

export const holidays: ResourceConfig = {
  resource: "holidays", title: "common:nav.holidays", help: "hints:page.holidays", createPerm: "subscriptions.manage", search: false, editable: true, deletable: true,
  columns: [{ key: "date", label: "common:f.date", render: (r) => dateOnly(r.date) }, { key: "name", label: "common:f.name" }],
  fields: [{ name: "date", label: "common:f.date", type: "date", required: true }, { name: "name", label: "common:f.name", type: "text", required: true }],
};

/* ---------------------------- CUSTOMERS ---------------------------- */
export const customers: ResourceConfig = {
  resource: "customers", title: "common:nav.customers", help: "hints:page.customers", createPerm: "customers.manage", editable: true, deletable: true, deleteLabel: "common:actions.deactivate",
  columns: [
    { key: "name", label: "common:f.name" }, { key: "phone", label: "common:f.phone" }, { key: "category", label: "masters:f.category", render: (r) => <Badge value={r.category} /> },
    { key: "price_group", label: "masters:f.priceGroup" }, { key: "discount_percent", label: "masters:f.discount", render: (r) => `${r.discount_percent}%` },
    { key: "outstanding", label: "orders:f.outstanding", render: (r) => money(r.outstanding), className: "text-right" }, { key: "loyalty_points", label: "masters:f.points" },
  ],
  filters: [{ name: "category", label: "masters:f.category", options: opt("household", "hotel") }],
  fields: [
    { name: "name", label: "common:f.name", type: "text", required: true }, { name: "phone", label: "common:f.phone", type: "text", required: true, hint: "hints:field.phone" }, { name: "email", label: "common:f.email", type: "text" },
    { name: "category", label: "masters:f.category", type: "select", default: "household", options: opt("household", "hotel") },
    { name: "price_group", label: "masters:f.priceGroup", type: "select", default: "household", options: groups, hint: "hints:field.priceGroup" },
    { name: "discount_percent", label: "masters:f.discount", type: "number", step: "0.01", hint: "hints:field.discount" }, { name: "gstin", label: "common:f.gstin", type: "text", hint: "hints:field.customerGstin" },
    { name: "address_line", label: "common:f.address", type: "textarea", createOnly: true, hint: "hints:field.firstAddress" },
    { name: "pincode", label: "masters:f.pincode", type: "text", createOnly: true },
    { name: "pin", label: "masters:f.pin", type: "map", createOnly: true, latKey: "address_latitude", lngKey: "address_longitude", hint: "hints:field.pin" },
    { name: "notes", label: "common:f.notes", type: "textarea" },
  ],
};

export const customerAddresses: ResourceConfig = {
  resource: "customer-addresses", title: "common:nav.addresses", help: "hints:page.addresses", createPerm: "customers.manage", editable: true, deletable: true,
  columns: [{ key: "customer_name", label: "common:f.customer" }, { key: "label", label: "common:f.name" }, { key: "address_line", label: "common:f.address" }, { key: "pincode", label: "masters:f.pincode" }, { key: "latitude", label: "masters:f.pin", render: (r) => (r.latitude ? "📍" : "–") }],
  fields: [
    { name: "customer", label: "common:f.customer", type: "select", required: true, createOnly: true, optionsFrom: { resource: "customers", label: (r) => `${r.name} (${r.phone})` } },
    { name: "label", label: "common:f.name", type: "text", default: "Home", hint: "hints:field.addressLabel" }, { name: "address_line", label: "common:f.address", type: "textarea", required: true },
    { name: "area", label: "masters:f.area", type: "text" }, { name: "pincode", label: "masters:f.pincode", type: "text" },
    { name: "pin", label: "masters:f.pin", type: "map", hint: "hints:field.pin" }, { name: "is_default", label: "masters:f.default", type: "checkbox" },
  ],
};

export const promotions: ResourceConfig = {
  resource: "promotions", title: "common:nav.promotions", help: "hints:page.promotions", createPerm: "promotions.manage", search: false, editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "buy_quantity", label: "masters:f.buy" }, { key: "free_quantity", label: "masters:f.free" }, { key: "valid_from", label: "masters:f.from", render: (r) => dateOnly(r.valid_from) }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "name", label: "common:f.name", type: "text", required: true }, { ...packageSel(), hint: "hints:field.promoPackage" },
    { name: "buy_quantity", label: "masters:f.buy", type: "number", step: "1", default: 5, hint: "hints:field.buyFree" }, { name: "free_quantity", label: "masters:f.free", type: "number", step: "1", default: 1 },
    { name: "valid_from", label: "masters:f.from", type: "date", required: true }, { name: "valid_to", label: "masters:f.to", type: "date" }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const coupons: ResourceConfig = {
  resource: "coupons", title: "common:nav.coupons", help: "hints:page.coupons", createPerm: "promotions.manage", editable: true, deletable: true,
  columns: [{ key: "code", label: "masters:f.code" }, { key: "discount_percent", label: "masters:f.discount", render: (r) => `${r.discount_percent}%` }, { key: "valid_from", label: "masters:f.from", render: (r) => dateOnly(r.valid_from) }, { key: "valid_to", label: "masters:f.to", render: (r) => dateOnly(r.valid_to) }, { key: "per_customer_limit", label: "masters:f.perCustomer" }],
  fields: [
    { name: "code", label: "masters:f.code", type: "text", required: true, hint: "hints:field.couponCode" }, { name: "discount_percent", label: "masters:f.discount", type: "number", step: "0.01", required: true },
    { name: "valid_from", label: "masters:f.from", type: "date", required: true }, { name: "valid_to", label: "masters:f.to", type: "date" },
    { name: "per_customer_limit", label: "masters:f.perCustomer", type: "number", step: "1", default: 1, hint: "hints:field.perCustomer" }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

/* --------------------- PRODUCTION, RECIPES, STOCK --------------------- */
export const productionBatches: ResourceConfig = {
  resource: "production-batches", title: "common:nav.production", help: "hints:page.production", createPerm: "production.create", createLabel: "production:new",
  columns: [
    { key: "batch_number", label: "production:f.batch" }, { key: "product_name", label: "common:f.product" }, { key: "location_name", label: "common:f.location" },
    { key: "quantity_produced", label: "production:f.produced", render: (r) => `${num(r.quantity_produced)} L`, className: "text-right" },
    { key: "expiry_date", label: "production:f.expiry", render: (r) => dateOnly(r.expiry_date) }, { key: "quality_passed", label: "production:f.quality", render: (r) => yes(r.quality_passed) },
  ],
  fields: [
    location(),
    { name: "recipe", label: "production:f.recipe", type: "select", required: true, hint: "hints:field.batchRecipe", optionsFrom: { resource: "recipes", label: (r) => r.name } },
    { name: "quantity_produced", label: "production:f.produced", type: "number", step: "0.001", required: true, hint: "hints:field.batchQty" },
    { name: "quality_passed", label: "production:f.quality", type: "checkbox", default: true, hint: "hints:field.qualityPassed" },
    { name: "notes", label: "common:f.notes", type: "textarea" },
  ],
  editable: true,
  editFields: [{ name: "notes", label: "common:f.notes", type: "textarea", hint: "hints:field.batchNotes" }, { name: "quality_notes", label: "production:f.qualityNotes", type: "textarea" }],
  formFooter: (v, _s, editing) => (editing ? null : <RecipeRequirements values={v} />),
  actions: [
    { label: "production:act.package", perm: "packaging.create", endpoint: (r) => `/production-batches/${r.id}/package/`,
      fields: (r) => [
        { name: "package", label: "common:f.package", type: "select", required: true, hint: "hints:field.packBatch", optionsFrom: { resource: "packages", params: { product: r.product }, label: (p) => `${p.product_name} ${p.name}` } },
        { name: "units", label: "production:f.units", type: "number", step: "1", required: true, hint: "hints:field.units" },
      ] },
  ],
};

const recipeFields: Field[] = [
  { name: "product", label: "common:f.product", type: "select", required: true, optionsFrom: { resource: "products", label: (r) => r.name } },
  { name: "name", label: "common:f.name", type: "text", required: true },
  { name: "output_quantity", label: "production:f.output", type: "number", step: "0.001", required: true, default: 100, hint: "hints:field.recipeOutput" },
  { name: "lines", label: "production:f.ingredients", type: "lines", hint: "hints:field.recipeLines", lines: [
    { name: "raw_material", label: "inventory:f.item", type: "select", optionsFrom: { resource: "raw-materials", label: (r) => r.name } },
    { name: "quantity", label: "common:f.quantity", type: "number", step: "0.001" },
    { name: "unit", label: "common:f.unit", type: "select", optionsFrom: { resource: "units", label: (r) => r.code } },
  ] },
  { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
];
export const recipes: ResourceConfig = {
  resource: "recipes", title: "common:nav.recipes", help: "hints:page.recipes", createPerm: "catalog.manage", search: false, editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "product_name", label: "common:f.product" }, { key: "output_quantity", label: "production:f.output", render: (r) => num(r.output_quantity) },
    { key: "lines", label: "production:f.ingredients", render: (r) => (r.lines as Row[]).map((l) => `${l.raw_material_name} ${num(l.quantity)} ${l.unit_code}`).join(", ") }],
  fields: recipeFields,
  toForm: (r) => ({ product: r.product, name: r.name, output_quantity: r.output_quantity, is_active: r.is_active, lines: r.lines.map((l: Row) => ({ raw_material: l.raw_material, quantity: String(l.quantity), unit: l.unit })) }),
};

export const stock: ResourceConfig = {
  resource: "stock", title: "common:nav.stock", help: "hints:page.stock",
  columns: [
    { key: "item_name", label: "inventory:f.item" }, { key: "location_name", label: "common:f.location" }, { key: "batch_number", label: "production:f.batch" },
    { key: "expiry_date", label: "production:f.expiry", render: (r) => dateOnly(r.expiry_date) },
    { key: "quantity", label: "common:f.quantity", render: (r) => `${num(r.quantity)} ${r.unit_code}`, className: "text-right" },
    { key: "reserved", label: "inventory:f.reserved", render: (r) => num(r.reserved), className: "text-right" },
    { key: "available", label: "inventory:f.available", render: (r) => num(r.available), className: "text-right" },
  ],
  filters: [{ name: "kind", label: "inventory:f.kind", options: [{ value: "raw", label: "inventory:kind.raw" }, { value: "bulk", label: "inventory:kind.bulk" }, { value: "packed", label: "inventory:kind.packed" }] }],
  actions: [
    { label: "inventory:act.adjust", perm: "inventory.adjust", endpoint: () => "/stock/adjust/", extra: (r) => ({ bucket: r.id }),
      fields: [
        { name: "movement_type", label: "common:f.type", type: "select", required: true, default: "wastage", options: ["adjustment", "wastage", "expiry", "damage"].map((v) => ({ value: v, label: `inventory:move.${v}` })) },
        { name: "quantity_delta", label: "inventory:f.delta", type: "number", step: "0.001", required: true, hint: "hints:field.delta" }, reasonField,
      ] },
    { label: "inventory:act.transfer", perm: "inventory.transfer", endpoint: () => "/stock/transfer/", extra: (r) => ({ bucket: r.id }),
      fields: [
        { name: "to_location", label: "inventory:f.toLocation", type: "select", required: true, hint: "hints:field.toLocation", optionsFrom: { resource: "locations", label: (r) => r.name } },
        { name: "quantity", label: "common:f.quantity", type: "number", step: "0.001", required: true }, { name: "note", label: "common:f.notes", type: "text" },
      ] },
  ],
};

export const stockMovements: ResourceConfig = {
  resource: "stock-movements", title: "common:nav.ledger", help: "hints:page.ledger", search: false,
  columns: [
    { key: "created_at", label: "common:f.date", render: (r) => dateTime(r.created_at) }, { key: "item_name", label: "inventory:f.item" }, { key: "location_name", label: "common:f.location" },
    { key: "movement_type", label: "common:f.type", render: (r) => <Badge value={r.movement_type} /> },
    { key: "quantity_delta", label: "inventory:f.delta", render: (r) => <span className={Number(r.quantity_delta) < 0 ? "text-danger" : "text-success"}>{Number(r.quantity_delta) > 0 ? "+" : ""}{num(r.quantity_delta)}</span>, className: "text-right" },
    { key: "balance_after", label: "inventory:f.balance", render: (r) => num(r.balance_after), className: "text-right" },
  ],
  filters: [{ name: "movement_type", label: "common:f.type", options: ["purchase", "production", "consumption", "packaging", "sale", "return", "transfer_out", "transfer_in", "adjustment", "wastage", "expiry", "damage"].map((v) => ({ value: v, label: `common:status.${v}` })) }],
};

export const rawMaterials: ResourceConfig = {
  resource: "raw-materials", title: "common:nav.rawMaterials", help: "hints:page.rawMaterials", createPerm: "inventory.create", editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "name_ta", label: "common:f.nameTa" }, { key: "unit_code", label: "common:f.unit" }, { key: "min_stock", label: "inventory:f.minStock", render: (r) => num(r.min_stock) }, { key: "is_packaging", label: "inventory:f.packaging", render: (r) => yes(r.is_packaging) }],
  fields: [
    { name: "name", label: "common:f.name", type: "text", required: true }, { name: "name_ta", label: "common:f.nameTa", type: "text", hint: "hints:field.nameTa" },
    { name: "unit", label: "common:f.unit", type: "select", required: true, hint: "hints:field.rawUnit", optionsFrom: { resource: "units", label: (r) => `${r.name} (${r.code})` } },
    { name: "min_stock", label: "inventory:f.minStock", type: "number", step: "0.001", hint: "hints:field.minStock" }, { name: "is_packaging", label: "inventory:f.packaging", type: "checkbox", hint: "hints:field.packagingMaterial" },
    { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const suppliers: ResourceConfig = {
  resource: "suppliers", title: "common:nav.suppliers", help: "hints:page.suppliers", createPerm: "purchasing.create", editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "phone", label: "common:f.phone" }, { key: "email", label: "common:f.email" }, { key: "gstin", label: "common:f.gstin" }],
  fields: [{ name: "name", label: "common:f.name", type: "text", required: true }, { name: "phone", label: "common:f.phone", type: "text" }, { name: "email", label: "common:f.email", type: "text" }, { name: "address", label: "common:f.address", type: "textarea" }, { name: "gstin", label: "common:f.gstin", type: "text" }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true }],
};

const purchaseFields: Field[] = [
  { name: "supplier", label: "inventory:f.supplier", type: "select", required: true, optionsFrom: { resource: "suppliers", label: (r) => r.name } }, location(),
  { name: "invoice_number", label: "orders:f.invoice", type: "text", hint: "hints:field.supplierInvoice" }, { name: "purchase_date", label: "common:f.date", type: "date", required: true },
  { name: "lines", label: "orders:f.items", type: "lines", hint: "hints:field.purchaseLines", lines: [
    { name: "raw_material", label: "inventory:f.item", type: "select", optionsFrom: { resource: "raw-materials", label: (r) => `${r.name} (${r.unit_code})` } },
    { name: "quantity", label: "common:f.quantity", type: "number" }, { name: "unit_cost", label: "inventory:f.unitCost", type: "number", step: "0.01" },
  ] },
];
export const purchases: ResourceConfig = {
  resource: "purchases", title: "common:nav.purchases", help: "hints:page.purchases", createPerm: "purchasing.create", createLabel: "inventory:newPurchase",
  columns: [
    { key: "invoice_number", label: "orders:f.invoice" }, { key: "supplier_name", label: "inventory:f.supplier" }, { key: "purchase_date", label: "common:f.date", render: (r) => dateOnly(r.purchase_date) },
    { key: "total", label: "common:f.total", render: (r) => money(r.total), className: "text-right" }, { key: "balance", label: "orders:f.outstanding", render: (r) => money(r.balance), className: "text-right" },
    { key: "status", label: "common:f.status", render: status("status") },
  ],
  fields: purchaseFields, editable: (r) => r.status === "draft", deletable: (r) => r.status === "draft",
  toForm: (r) => ({ supplier: r.supplier, location: r.location, invoice_number: r.invoice_number, purchase_date: r.purchase_date, lines: r.lines.map((l: Row) => ({ raw_material: l.raw_material, quantity: String(l.quantity), unit_cost: String(l.unit_cost) })) }),
  actions: [
    { label: "inventory:act.receive", perm: "purchasing.create", show: (r) => r.status === "draft", endpoint: (r) => `/purchases/${r.id}/receive/`, confirmText: "inventory:confirmReceive" },
    { label: "orders:act.pay", perm: "purchasing.pay", show: (r) => r.status === "received" && Number(r.balance) > 0, endpoint: (r) => `/purchases/${r.id}/pay/`,
      fields: (r) => [
        { name: "amount", label: "common:f.amount", type: "number", step: "0.01", required: true, default: r.balance }, { name: "method", label: "orders:f.method", type: "select", default: "cash", options: methods },
        { name: "paid_on", label: "common:f.date", type: "date", required: true, default: new Date().toISOString().slice(0, 10) }, { name: "reference", label: "orders:f.reference", type: "text" },
      ] },
  ],
};

/* ----------------------------- CATALOGUE ----------------------------- */
export const units: ResourceConfig = {
  resource: "units", title: "common:nav.units", help: "hints:page.units", createPerm: "catalog.manage", search: false, editable: true, deletable: true,
  columns: [{ key: "code", label: "masters:f.code" }, { key: "name", label: "common:f.name" }, { key: "name_ta", label: "common:f.nameTa" }, { key: "kind", label: "common:f.type" }, { key: "factor", label: "masters:f.factor", render: (r) => num(r.factor) }],
  fields: [
    { name: "code", label: "masters:f.code", type: "text", required: true }, { name: "name", label: "common:f.name", type: "text", required: true }, { name: "name_ta", label: "common:f.nameTa", type: "text" },
    { name: "kind", label: "common:f.type", type: "select", required: true, options: [{ value: "volume", label: "masters:kind.volume" }, { value: "weight", label: "masters:kind.weight" }, { value: "count", label: "masters:kind.count" }] },
    { name: "factor", label: "masters:f.factor", type: "number", step: "0.000001", required: true, hint: "hints:field.unitFactor" },
  ],
};

export const products: ResourceConfig = {
  resource: "products", title: "common:nav.products", help: "hints:page.products", createPerm: "catalog.manage", editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "name_ta", label: "common:f.nameTa" }, { key: "product_type", label: "common:f.type" }, { key: "base_unit_code", label: "common:f.unit" }, { key: "gst_rate", label: "masters:f.gst", render: (r) => `${r.gst_rate}%` }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "name", label: "common:f.name", type: "text", required: true }, { name: "name_ta", label: "common:f.nameTa", type: "text", hint: "hints:field.nameTa" },
    { name: "product_type", label: "common:f.type", type: "select", default: "idli", options: [{ value: "idli", label: "masters:type.idli" }, { value: "dosa", label: "masters:type.dosa" }, { value: "other", label: "masters:type.other" }] },
    { name: "base_unit", label: "masters:f.baseUnit", type: "select", required: true, hint: "hints:field.baseUnit", optionsFrom: { resource: "units", label: (r) => `${r.name} (${r.code})` } },
    { name: "density_kg_per_litre", label: "masters:f.density", type: "number", step: "0.001", hint: "hints:field.density" },
    { name: "hsn_code", label: "masters:f.hsn", type: "text", default: "2106", hint: "hints:field.hsn" }, { name: "gst_rate", label: "masters:f.gst", type: "number", step: "0.01", default: "5.00", hint: "hints:field.gst" },
    { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const packages: ResourceConfig = {
  resource: "packages", title: "common:nav.packages", help: "hints:page.packages", createPerm: "catalog.manage", editable: true, deletable: true,
  columns: [{ key: "product_name", label: "common:f.product" }, { key: "name", label: "common:f.name" }, { key: "size", label: "masters:f.size", render: (r) => num(r.size) }, { key: "unit_code", label: "common:f.unit" }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "product", label: "common:f.product", type: "select", required: true, optionsFrom: { resource: "products", label: (r) => r.name } },
    { name: "name", label: "common:f.name", type: "text", required: true, hint: "hints:field.packageName" }, { name: "size", label: "masters:f.size", type: "number", step: "0.001", required: true },
    { name: "unit", label: "common:f.unit", type: "select", required: true, hint: "hints:field.packageUnit", optionsFrom: { resource: "units", label: (r) => `${r.name} (${r.code})` } }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const prices: ResourceConfig = {
  resource: "prices", title: "common:nav.prices", help: "hints:page.prices", createPerm: "catalog.manage", search: false, editable: true, deletable: true,
  columns: [{ key: "package_name", label: "common:f.package" }, { key: "price_group", label: "masters:f.priceGroup" }, { key: "amount", label: "common:f.price", render: (r) => money(r.amount), className: "text-right" }, { key: "effective_from", label: "masters:f.from", render: (r) => dateOnly(r.effective_from) }, { key: "effective_to", label: "masters:f.to", render: (r) => dateOnly(r.effective_to) }],
  filters: [{ name: "price_group", label: "masters:f.priceGroup", options: groups }],
  fields: [
    { ...packageSel(), required: true }, { name: "price_group", label: "masters:f.priceGroup", type: "select", default: "household", options: groups, hint: "hints:field.priceGroup" },
    { name: "amount", label: "common:f.price", type: "number", step: "0.01", required: true, hint: "hints:field.priceAmount" },
    { name: "effective_from", label: "masters:f.from", type: "date", required: true, hint: "hints:field.effectiveFrom" }, { name: "effective_to", label: "masters:f.to", type: "date" },
  ],
};

/* ------------------------------ DELIVERY ------------------------------ */
export const deliveries: ResourceConfig = {
  resource: "delivery/assignments", title: "common:nav.delivery", help: "hints:page.delivery", createPerm: "delivery.assign", createLabel: "delivery:assign", createPath: "/delivery/assignments/assign/", search: false,
  columns: [
    { key: "route_sequence", label: "delivery:f.stop" }, { key: "order_number", label: "orders:f.number" }, { key: "customer_name", label: "common:f.customer" }, { key: "customer_phone", label: "common:f.phone", render: (r) => <a className="text-info underline" href={`tel:${r.customer_phone}`}>{r.customer_phone}</a> },
    { key: "address", label: "common:f.address" }, { key: "order_total", label: "common:f.total", render: (r) => money(r.order_total) },
    { key: "payment_status", label: "orders:f.payment", render: status("payment_status") }, { key: "status", label: "common:f.status", render: status("status") },
    { key: "navigation_url", label: "delivery:f.navigate", render: (r) => (r.navigation_url ? <a className="btn-outline btn-sm" href={r.navigation_url} target="_blank" rel="noreferrer">↗ {`Maps`}</a> : null) },
  ],
  fields: [
    { name: "order", label: "orders:f.number", type: "select", required: true, hint: "hints:field.assignOrder", optionsFrom: { resource: "orders", params: { status: "dispatched" }, label: (r) => `${r.order_number}: ${r.customer_name}` } },
    { name: "employee", label: "delivery:f.employee", type: "select", required: true, optionsFrom: { resource: "users", label: (r) => r.username } },
    { name: "route_sequence", label: "delivery:f.stop", type: "number", step: "1", default: 1, hint: "hints:field.stop" },
  ],
  actions: [
    { label: "delivery:act.delivered", perm: "delivery.record", show: (r) => r.status !== "delivered", endpoint: (r) => `/delivery/assignments/${r.id}/record/`, extra: () => ({ outcome: "delivered" }), fields: [{ name: "customer_confirmed", label: "delivery:f.confirmed", type: "checkbox", default: true }, { name: "proof_note", label: "delivery:f.proof", type: "text", hint: "hints:field.proof" }] },
    { label: "delivery:act.failed", perm: "delivery.record", danger: true, show: (r) => r.status === "assigned", endpoint: (r) => `/delivery/assignments/${r.id}/record/`, extra: () => ({ outcome: "failed" }), fields: [{ name: "failed_reason", label: "delivery:f.failReason", type: "text", required: true }] },
    { label: "delivery:act.collect", perm: "delivery.record", show: (r) => r.payment_status !== "paid", endpoint: (r) => `/delivery/assignments/${r.id}/collect/`,
      fields: (r) => [
        { name: "method", label: "orders:f.method", type: "select", default: "cash", options: methods.slice(0, 2) }, { name: "amount", label: "common:f.amount", type: "number", step: "0.01", required: true, default: r.order_total },
        { name: "tender_amount", label: "orders:f.tender", type: "number", step: "0.01", hint: "hints:field.tender" }, { name: "reference", label: "orders:f.reference", type: "text", hint: "hints:field.reference" },
      ] },
  ],
};

export const feeSlabs: ResourceConfig = {
  resource: "delivery/fee-slabs", title: "delivery:slabs", help: "hints:page.slabs", createPerm: "delivery.fees", createLabel: "delivery:newSlab", search: false, editable: true, deletable: true,
  columns: [
    { key: "location_name", label: "common:f.location" }, { key: "label", label: "common:f.name" },
    { key: "min_km", label: "delivery:range", render: (r) => `${num(r.min_km, 1)} – ${r.max_km ? num(r.max_km, 1) : "∞"} km` },
    { key: "base_fee", label: "delivery:baseFee", render: (r) => money(r.base_fee), className: "text-right" }, { key: "per_km_fee", label: "delivery:perKm", render: (r) => money(r.per_km_fee), className: "text-right" },
    { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) },
  ],
  fields: [
    location(), { name: "label", label: "common:f.name", type: "text", hint: "hints:field.slabLabel" },
    { name: "min_km", label: "delivery:minKm", type: "number", step: "0.1", required: true, default: 0, hint: "hints:field.slabMin" }, { name: "max_km", label: "delivery:maxKm", type: "number", step: "0.1", hint: "hints:field.slabMax" },
    { name: "base_fee", label: "delivery:baseFee", type: "number", step: "0.01", required: true, hint: "hints:field.slabBase" }, { name: "per_km_fee", label: "delivery:perKm", type: "number", step: "0.01", hint: "hints:field.slabPerKm" },
    { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const surgeRules: ResourceConfig = {
  resource: "delivery/surge-rules", title: "delivery:surge", help: "hints:page.surge", createPerm: "delivery.fees", createLabel: "delivery:newSurge", search: false, editable: true, deletable: true,
  columns: [
    { key: "location_name", label: "common:f.location" }, { key: "label", label: "common:f.name" }, { key: "min_orders", label: "delivery:minOrders" },
    { key: "value", label: "delivery:surcharge", render: (r) => (r.surcharge_type === "percent" ? `+${r.value}%` : `+${money(r.value)}`) }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) },
  ],
  fields: [
    location(), { name: "label", label: "common:f.name", type: "text" },
    { name: "min_orders", label: "delivery:minOrders", type: "number", step: "1", required: true, hint: "hints:field.surgeMin" },
    { name: "surcharge_type", label: "delivery:surgeType", type: "select", required: true, default: "percent", options: [{ value: "percent", label: "delivery:typePercent" }, { value: "flat", label: "delivery:typeFlat" }], hint: "hints:field.surgeType" },
    { name: "value", label: "delivery:surgeValue", type: "number", step: "0.01", required: true, hint: "hints:field.surgeValue" }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

/* ------------------------------ PEOPLE ------------------------------ */
export const attendance: ResourceConfig = {
  resource: "attendance", title: "common:nav.attendance", help: "hints:page.attendance", createPerm: "employees.manage", createLabel: "common:attendance.addManual", editable: true, deletable: true, deleteNeedsReason: true,
  columns: [
    { key: "date", label: "common:f.date", render: (r) => dateOnly(r.date) }, { key: "user_name", label: "masters:f.user" }, { key: "location_name", label: "common:f.location" },
    { key: "check_in", label: "common:attendance.in", render: (r) => dateTime(r.check_in) }, { key: "check_out", label: "common:attendance.out", render: (r) => (r.check_out ? dateTime(r.check_out) : <span className="text-warning">{"—"}</span>) },
    { key: "hours", label: "common:attendance.hours", render: (r) => (r.hours != null ? num(r.hours, 2) : "–") }, { key: "source", label: "common:attendance.source", render: (r) => (r.source === "manual" ? "✎" : "") },
  ],
  fields: [
    { name: "user", label: "masters:f.user", type: "select", required: true, createOnly: true, optionsFrom: { resource: "users", label: (r) => r.username } }, location({ createOnly: true }),
    { name: "date", label: "common:f.date", type: "date", required: true, createOnly: true }, { name: "check_in", label: "common:attendance.in", type: "datetime", required: true }, { name: "check_out", label: "common:attendance.out", type: "datetime", hint: "hints:field.checkOut" },
    { name: "reason", label: "common:f.reason", type: "text", required: true, hint: "hints:field.attendanceReason" },
  ],
  toForm: (r) => ({ check_in: r.check_in?.slice(0, 16) ?? "", check_out: r.check_out?.slice(0, 16) ?? "", reason: "" }),
  filters: [],
};

export const employees: ResourceConfig = {
  resource: "employees", title: "common:nav.employees", help: "hints:page.employees", createPerm: "employees.manage", editable: true, deletable: true,
  columns: [{ key: "name", label: "common:f.name" }, { key: "job_title", label: "masters:f.jobTitle" }, { key: "joining_date", label: "masters:f.joined", render: (r) => dateOnly(r.joining_date) }, { key: "salary_type", label: "masters:f.salaryType", render: (r) => r.salary_type ?? "" }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "user", label: "masters:f.user", type: "select", required: true, createOnly: true, hint: "hints:field.empUser", optionsFrom: { resource: "users", label: (r) => r.username } }, location(),
    { name: "job_title", label: "masters:f.jobTitle", type: "text", required: true }, { name: "joining_date", label: "masters:f.joined", type: "date", required: true },
    { name: "salary_type", label: "masters:f.salaryType", type: "select", default: "monthly", hint: "hints:field.salaryType", options: [{ value: "monthly", label: "masters:salary.monthly" }, { value: "hourly", label: "masters:salary.hourly" }] },
    { name: "base_salary", label: "masters:f.salary", type: "number", step: "0.01", hint: "hints:field.salary" }, { name: "hourly_rate", label: "masters:f.hourly", type: "number", step: "0.01", hint: "hints:field.hourly" },
    { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const payroll: ResourceConfig = {
  resource: "payroll", title: "common:nav.payroll", help: "hints:page.payroll", createPerm: "payroll.manage", createLabel: "common:payroll.addEntry", search: false,
  columns: [
    { key: "period", label: "masters:f.period", render: (r) => dateOnly(r.period) }, { key: "user_name", label: "masters:f.user" },
    { key: "entry_type", label: "common:f.type", render: (r) => <span className={r.is_void ? "line-through opacity-60" : ""}>{r.entry_type}{r.is_auto ? " ⚙" : ""}</span> },
    { key: "amount", label: "common:f.amount", render: (r) => <span className={r.is_void ? "line-through opacity-60" : ""}>{money(r.amount)}</span>, className: "text-right" }, { key: "note", label: "common:f.notes" },
  ],
  fields: [
    { name: "user", label: "masters:f.user", type: "select", required: true, optionsFrom: { resource: "users", label: (r) => r.username } }, location(),
    { name: "entry_type", label: "common:f.type", type: "select", default: "advance", hint: "hints:field.payType", options: ["advance", "bonus", "deduction"].map((v) => ({ value: v, label: `masters:pay.${v}` })) },
    { name: "amount", label: "common:f.amount", type: "number", step: "0.01", required: true }, { name: "period", label: "masters:f.period", type: "date", required: true, hint: "hints:field.payPeriod" }, { name: "note", label: "common:f.notes", type: "text" },
  ],
  actions: [{ label: "masters:act.void", perm: "payroll.manage", danger: true, show: (r) => !r.is_void, endpoint: (r) => `/payroll/${r.id}/void/`, fields: [reasonField] }],
};

const roleOptions = ["location_admin", "production_manager", "production_employee", "inventory_manager", "accountant", "delivery_manager", "delivery_employee"].map((v) => ({ value: v, label: `common:roles.${v}` }));

export const users: ResourceConfig = {
  resource: "users", title: "common:nav.users", help: "hints:page.users", createPerm: "employees.manage", editable: true, deletable: true, deleteLabel: "common:actions.deactivate",
  columns: [{ key: "username", label: "masters:f.username" }, { key: "first_name", label: "common:f.name" }, { key: "phone", label: "common:f.phone" }, { key: "preferred_language", label: "masters:f.language" }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "username", label: "masters:f.username", type: "text", required: true, createOnly: true, hint: "hints:field.username" }, { name: "first_name", label: "common:f.name", type: "text" }, { name: "phone", label: "common:f.phone", type: "text" },
    { name: "password", label: "common:auth.password", type: "password", hint: "hints:field.password" },
    { name: "preferred_language", label: "masters:f.language", type: "select", default: "en", options: [{ value: "en", label: "English" }, { value: "ta", label: "தமிழ்" }] }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const memberships: ResourceConfig = {
  resource: "memberships", title: "common:nav.access", help: "hints:page.access", createPerm: "employees.manage", search: false, editable: true, deletable: true, deleteLabel: "common:actions.revoke",
  columns: [{ key: "user_name", label: "masters:f.user" }, { key: "location_name", label: "common:f.location" }, { key: "role", label: "masters:f.role", render: (r) => <Badge value={r.role} /> }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "user", label: "masters:f.user", type: "select", required: true, createOnly: true, optionsFrom: { resource: "users", label: (r) => r.username } }, location({ createOnly: true }),
    { name: "role", label: "masters:f.role", type: "select", required: true, hint: "hints:field.role", options: roleOptions }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

/* ------------------------------ FINANCE / ADMIN ------------------------------ */
export const expenses: ResourceConfig = {
  resource: "expenses", title: "common:nav.expenses", help: "hints:page.expenses", createPerm: "expenses.create", editable: (r) => !r.is_void,
  columns: [{ key: "expense_date", label: "common:f.date", render: (r) => dateOnly(r.expense_date) }, { key: "location_name", label: "common:f.location" }, { key: "category", label: "masters:f.category" }, { key: "amount", label: "common:f.amount", render: (r) => <span className={r.is_void ? "line-through opacity-60" : ""}>{money(r.amount)}</span>, className: "text-right" }, { key: "description", label: "common:f.notes" }],
  fields: [
    location(), { name: "category", label: "masters:f.category", type: "select", default: "other", hint: "hints:field.expenseCategory", options: ["packaging", "fuel", "vehicle", "electricity", "rent", "delivery", "raw_material", "other"].map((v) => ({ value: v, label: `masters:cat.${v}` })) },
    { name: "amount", label: "common:f.amount", type: "number", step: "0.01", required: true }, { name: "expense_date", label: "common:f.date", type: "date", required: true },
    { name: "paid_via", label: "orders:f.method", type: "select", default: "cash", options: methods }, { name: "description", label: "common:f.notes", type: "text" },
  ],
  actions: [{ label: "masters:act.void", perm: "expenses.create", danger: true, show: (r) => !r.is_void, endpoint: (r) => `/expenses/${r.id}/void/`, fields: [reasonField] }],
};

export const locations: ResourceConfig = {
  resource: "locations", title: "common:nav.locations", help: "hints:page.locations", createPerm: "locations.manage", editable: true, deletable: true, deleteLabel: "common:actions.deactivate",
  columns: [{ key: "name", label: "common:f.name" }, { key: "code", label: "masters:f.code" }, { key: "address", label: "common:f.address" }, { key: "latitude", label: "masters:f.pin", render: (r) => (r.latitude ? "📍" : "–") }, { key: "is_active", label: "common:status.active", render: (r) => yes(r.is_active) }],
  fields: [
    { name: "name", label: "common:f.name", type: "text", required: true }, { name: "code", label: "masters:f.code", type: "text", required: true, hint: "hints:field.locCode" },
    { name: "address", label: "common:f.address", type: "textarea" }, { name: "phone", label: "common:f.phone", type: "text" },
    { name: "pin", label: "masters:f.pin", type: "map", hint: "hints:field.locPin" }, { name: "is_active", label: "common:status.active", type: "checkbox", default: true },
  ],
};

export const auditLogs: ResourceConfig = {
  resource: "audit-logs", title: "common:nav.audit", help: "hints:page.audit",
  columns: [{ key: "created_at", label: "common:f.date", render: (r) => dateTime(r.created_at) }, { key: "user_name", label: "masters:f.user" }, { key: "action", label: "masters:f.action" }, { key: "entity_type", label: "masters:f.entity" }, { key: "reason", label: "common:f.reason" }],
};
