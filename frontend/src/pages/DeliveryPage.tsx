import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";
import ResourcePage from "../components/ResourcePage";
import { ErrorBox } from "../components/ui";
import { api, errorMessage } from "../lib/api";
import { useFeedback } from "../components/feedback";
import { deliveries } from "./resources";

/** Duty session: GPS is sent only while the employee has agreed AND the app is open.
 *  (A PWA cannot track reliably in the background, especially on iPhone.) */
function DutyPanel() {
  const { t } = useTranslation();
  const fb = useFeedback();
  const [watchId, setWatchId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const start = async () => {
    setError("");
    if (!(await fb.confirm({ message: t("delivery:consentText") }))) return;
    try {
      await api.post("/delivery/duty/", { action: "start", consent: true });
      const id = navigator.geolocation.watchPosition(
        (pos) => { api.post("/delivery/duty/", { action: "ping", latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy }).catch(() => undefined); },
        (err) => setError(err.message), { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 });
      setWatchId(id);
    } catch (e) { setError(errorMessage(e)); }
  };
  const stop = async () => {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    setWatchId(null);
    try { await api.post("/delivery/duty/", { action: "end" }); } catch (e) { setError(errorMessage(e)); }
  };

  return (
    <div className="card flex flex-wrap items-center gap-3">
      <div className="flex-1 text-sm"><b>{t("delivery:duty")}</b><div className="text-muted">{watchId === null ? t("delivery:dutyOff") : t("delivery:dutyOn")}</div></div>
      {watchId === null ? <button className="btn-accent" onClick={start}>{t("delivery:startDuty")}</button> : <button className="btn-outline" onClick={stop}>{t("delivery:endDuty")}</button>}
      {error && <div className="w-full"><ErrorBox message={error} /></div>}
    </div>
  );
}

export default function DeliveryPage() {
  const { can } = useAuth();
  return <ResourcePage cfg={{ ...deliveries, header: can("delivery.record") ? <DutyPanel /> : undefined }} />;
}
