import L from "leaflet";
import { LocateFixed, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

export interface Pin { lat: number | null; lng: number | null }

const DEFAULT_CENTER: [number, number] = [9.4533, 77.8024]; // Sivakasi
const icon = L.divIcon({
  className: "",
  html: '<div style="width:26px;height:26px;border-radius:50% 50% 50% 0;background:rgb(var(--color-accent));border:3px solid rgb(var(--color-primary));transform:rotate(-45deg);box-shadow:0 2px 6px rgba(0,0,0,.4)"></div>',
  iconSize: [26, 26], iconAnchor: [13, 26],
});

/** Click the map, drag the pin, search a place, or use the phone's GPS. Map data (c) OpenStreetMap contributors. */
export default function LocationPicker({ value, onChange }: { value: Pin; onChange: (p: Pin) => void }) {
  const { t } = useTranslation();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.Marker | null>(null);
  const [query, setQuery] = useState("");
  const [msg, setMsg] = useState("");
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const place = (lat: number, lng: number, fly = false) => {
    if (!map.current) return;
    if (!marker.current) {
      marker.current = L.marker([lat, lng], { icon, draggable: true }).addTo(map.current);
      marker.current.on("dragend", () => { const p = marker.current!.getLatLng(); onChangeRef.current({ lat: +p.lat.toFixed(6), lng: +p.lng.toFixed(6) }); });
    } else marker.current.setLatLng([lat, lng]);
    if (fly) map.current.setView([lat, lng], Math.max(map.current.getZoom(), 16));
  };

  useEffect(() => {
    if (!el.current || map.current) return;
    const start: [number, number] = value.lat != null && value.lng != null ? [value.lat, value.lng] : DEFAULT_CENTER;
    map.current = L.map(el.current, { center: start, zoom: value.lat != null ? 16 : 13 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map.current);
    if (value.lat != null && value.lng != null) place(value.lat, value.lng);
    map.current.on("click", (e: L.LeafletMouseEvent) => { place(e.latlng.lat, e.latlng.lng); onChangeRef.current({ lat: +e.latlng.lat.toFixed(6), lng: +e.latlng.lng.toFixed(6) }); });
    setTimeout(() => map.current?.invalidateSize(), 200); // the map is usually opened inside a modal
    return () => { map.current?.remove(); map.current = null; marker.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const useMyLocation = () => {
    setMsg("");
    if (!navigator.geolocation) return setMsg(t("common:map.noGps"));
    navigator.geolocation.getCurrentPosition(
      (pos) => { const lat = +pos.coords.latitude.toFixed(6), lng = +pos.coords.longitude.toFixed(6); place(lat, lng, true); onChange({ lat, lng }); },
      () => setMsg(t("common:map.gpsDenied")), { enableHighAccuracy: true, timeout: 15000 });
  };

  const search = async () => {
    if (!query.trim()) return;
    setMsg("");
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=in&q=${encodeURIComponent(query)}`);
      const j = (await r.json()) as { lat: string; lon: string }[];
      if (!j.length) return setMsg(t("common:map.notFound"));
      const lat = +(+j[0].lat).toFixed(6), lng = +(+j[0].lon).toFixed(6);
      place(lat, lng, true); onChange({ lat, lng });
    } catch { setMsg(t("common:map.searchFailed")); }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input className="input" placeholder={t("common:map.search")} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); search(); } }} />
        <button type="button" className="btn-outline" onClick={search} aria-label={t("common:map.searchBtn")}><Search size={16} /></button>
        <button type="button" className="btn-outline" onClick={useMyLocation}><LocateFixed size={16} /><span className="hidden sm:inline">{t("common:map.useMine")}</span></button>
      </div>
      <div ref={el} className="h-64 w-full overflow-hidden rounded-xl border border-border sm:h-72" />
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{value.lat != null && value.lng != null ? `📍 ${value.lat}, ${value.lng}` : t("common:map.tapHint")}</span>
        {value.lat != null && <button type="button" className="underline" onClick={() => { marker.current?.remove(); marker.current = null; onChange({ lat: null, lng: null }); }}>{t("common:map.clear")}</button>}
      </div>
      {msg && <div className="text-xs text-danger">{msg}</div>}
    </div>
  );
}
