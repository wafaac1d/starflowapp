import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  ApiRequestError,
  createBillingOrder,
  getBilling,
  postInvoiceStatus,
  type BillingResponse,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { invoiceGrantsPremium, openInvoice } from "../telegram";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { ListRow } from "../shared/ui/ListRow/ListRow";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./screens.module.css";

const BENEFITS = [
  {
    icon: "premium_personal_forecasts" as const,
    title: "Персональные прогнозы",
    subtitle: "На основе вашей натальной карты",
  },
  {
    icon: "premium_natal_chart" as const,
    title: "Натальная карта",
    subtitle: "Подробная интерпретация",
  },
  {
    icon: "premium_astro_assistant" as const,
    title: "Астропомощник",
    subtitle: "Больше вопросов и тем",
  },
];

export function PremiumScreen() {
  const [notice, setNotice] = useState("");
  const billing = useQuery({ queryKey: queryKeys.billing, queryFn: () => getBilling() });
  const pay = useMutation({
    mutationFn: async () => {
      const key = rememberKey();
      let ticket = await createBillingOrder("subscription", key);
      for (let attempt = 0; attempt < 5 && waiting(ticket); attempt += 1) {
        await delay(400);
        ticket = await createBillingOrder("subscription", key);
      }
      const link = ticket.subscription_invoice_link;
      const orderId = ticket.subscription_order_id;
      if (link === null || orderId === null) {
        setNotice("Оплата Stars недоступна в этой сессии.");
        return;
      }
      const status = await openInvoice(link);
      if (invoiceGrantsPremium(status)) {
        throw new Error("invoice status must not grant premium");
      }
      if (status === "unavailable") {
        setNotice("Оплата Stars недоступна в этой сессии.");
        return;
      }
      await postInvoiceStatus(orderId, status);
    },
    onError: (error) => {
      setNotice(error instanceof ApiRequestError ? error.message : "Не удалось открыть счёт");
    },
  });
  const price = billing.data?.price_stars ?? 250;
  const days = billing.data?.period_days ?? 30;
  return (
    <Screen>
      <img className={styles.premiumArt} src="/illustrations/png/constellation_premium.png" alt="" />
      <TopBar back />
      <h1 className={styles.welcomeTitle}>Больше о себе</h1>
      <p className={styles.lead}>Расширьте возможности StarFlow и получите более глубокий анализ.</p>
      <div className={styles.stack}>
        {BENEFITS.map((item) => (
          <ListRow key={item.title} icon={item.icon} title={item.title} subtitle={item.subtitle} />
        ))}
      </div>
      <hr className={styles.rule} />
      <p className={styles.price}>
        <Icon name="stars_currency" size={18} />
        {price} звёзд / {days} дней
      </p>
      {notice !== "" ? <p role="status">{notice}</p> : null}
      <Button
        loading={pay.isPending}
        onClick={() => {
          pay.mutate();
        }}
      >
        Подключить
      </Button>
      <p className={styles.fine}>Автопродление, отмена в любой момент.</p>
    </Screen>
  );
}

function waiting(ticket: BillingResponse): boolean {
  return ticket.subscription_invoice_link === null && ticket.subscription_payment_state === "pending";
}

function rememberKey(): string {
  const existing = sessionStorage.getItem("starflow-invoice-subscription");
  if (existing !== null && existing.length >= 8) {
    return existing;
  }
  const created = crypto.randomUUID().replaceAll("-", "");
  sessionStorage.setItem("starflow-invoice-subscription", created);
  return created;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
