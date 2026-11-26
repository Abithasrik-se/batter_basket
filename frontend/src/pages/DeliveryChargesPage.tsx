import { useTranslation } from "react-i18next";
import ResourcePage from "../components/ResourcePage";
import { HelpBanner, PageHeader } from "../components/ui";
import { feeSlabs, surgeRules } from "./resources";

export default function DeliveryChargesPage() {
  const { t } = useTranslation();
  return (
    <div className="space-y-8">
      <PageHeader title={t("common:nav.deliveryCharges")} subtitle={t("hints:page.deliveryChargesSub")} />
      <HelpBanner id="delivery-charges" text="hints:page.deliveryCharges" />
      <ResourcePage cfg={{ ...feeSlabs, embedded: true }} />
      <ResourcePage cfg={{ ...surgeRules, embedded: true }} />
    </div>
  );
}
