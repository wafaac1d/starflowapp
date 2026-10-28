import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { Link } from "react-router";

import { ApiRequestError, createTopup, postInvoiceStatus } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Field } from "../shared/ui/Field/Field";
import { invoiceGrantsPremium, openInvoice } from "../telegram";
import styles from "./TopUpDialog.module.css";

const PRESETS = [10, 20, 50, 100] as const;

type TopUpDialogProps = {
  balance: number | null;
  onClose: () => void;
};

export function TopUpDialog({ balance, onClose }: TopUpDialogProps) {
  const titleId = useId();
  const queryClient = useQueryClient();
  const [preset, setPreset] = useState<(typeof PRESETS)[number]>(10);
  const [custom, setCustom] = useState("");
  const [notice, setNotice] = useState("");
  const amount = chosenAmount(preset, custom);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);
  const pay = useMutation({
    mutationFn: async (stars: number) => {
      const key = crypto.randomUUID().replaceAll("-", "");
      const ticket = await createTopup(stars, key);
      const status = await openInvoice(ticket.invoice_link);
      if (invoiceGrantsPremium(status)) {
        throw new Error("invoice status must not grant premium");
      }
      if (status === "unavailable") {
        throw new Error("Оплата Stars недоступна в этой сессии.");
      }
      await postInvoiceStatus(ticket.order_id, status);
      await queryClient.invalidateQueries({ queryKey: queryKeys.session });
    },
    onSuccess: () => {
      setNotice("Баланс обновится, когда Telegram подтвердит оплату.");
    },
    onError: (error) => {
      setNotice(error instanceof ApiRequestError ? error.message : "Не удалось открыть счёт");
    },
  });
  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => {
          event.stopPropagation();
        }}
      >
        <h2 id={titleId} className={styles.title}>
          Пополнение
        </h2>
        {balance !== null ? <p className={styles.body}>Сейчас на балансе {balance}.</p> : null}
        <div className={styles.presets}>
          {PRESETS.map((value) => (
            <button
              key={value}
              type="button"
              className={styles.preset}
              aria-pressed={custom.trim() === "" && preset === value}
              onClick={() => {
                setCustom("");
                setPreset(value);
              }}
            >
              {value}
            </button>
          ))}
        </div>
        <Field
          label="Своя сумма"
          value={custom}
          chevron={false}
          onChange={(value) => {
            setCustom(value.replaceAll(/[^\d]/g, ""));
          }}
        />
        <Button
          disabled={amount === null}
          loading={pay.isPending}
          onClick={() => {
            if (amount === null) {
              return;
            }
            setNotice("");
            pay.mutate(amount);
          }}
        >
          Оплатить
        </Button>
        {notice !== "" ? <p className={styles.notice}>{notice}</p> : null}
        <p className={styles.body}>
          Можно подключить <Link to="/premium">Premium</Link>. Тогда карта, совместимость и вопросы
          входят в период.
        </p>
        <p className={styles.body}>
          Звёзды Telegram покупаются в{" "}
          <a href="https://t.me/PremiumBot" target="_blank" rel="noreferrer">
            t.me/PremiumBot
          </a>
          .
        </p>
        <Button variant="secondary" onClick={onClose}>
          Закрыть
        </Button>
      </div>
    </div>
  );
}

function chosenAmount(preset: number, custom: string): number | null {
  const trimmed = custom.trim();
  if (trimmed !== "") {
    if (!/^\d+$/.test(trimmed)) {
      return null;
    }
    const value = Number(trimmed);
    if (value < 1 || value > 10000) {
      return null;
    }
    return value;
  }
  return preset;
}
