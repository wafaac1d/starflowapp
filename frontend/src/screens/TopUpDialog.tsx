import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import { ApiRequestError, createTopup, postInvoiceStatus, redeemBalanceCode } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Dialog } from "../shared/ui/Dialog/Dialog";
import { Field } from "../shared/ui/Field/Field";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { invoiceGrantsPremium, openInvoice } from "../telegram";
import styles from "./TopUpDialog.module.css";

const PRESETS = [10, 20, 50, 100] as const;

type TopUpDialogProps = {
  balance: number | null;
  onClose: () => void;
};

export function TopUpDialog({ balance, onClose }: TopUpDialogProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [preset, setPreset] = useState<(typeof PRESETS)[number]>(10);
  const [custom, setCustom] = useState("");
  const [notice, setNotice] = useState("");
  const [code, setCode] = useState("");
  const amount = chosenAmount(preset, custom);
  const redeem = useMutation({
    mutationFn: () => redeemBalanceCode(code.trim()),
    onSuccess: async () => {
      setCode("");
      setNotice("Код зачислил звёзды на баланс.");
      await queryClient.invalidateQueries({ queryKey: queryKeys.session });
    },
    onError: (error) => {
      setNotice(error instanceof ApiRequestError ? error.message : "Код не подошёл");
    },
  });
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
  const balanceLine =
    balance !== null ? (
      <>
        Сейчас на балансе <StarPrice amount={balance} />.
      </>
    ) : undefined;
  return (
    <Dialog
      title="Пополнение"
      icon="stars_currency"
      onClose={onClose}
      {...(balanceLine !== undefined ? { subtitle: balanceLine } : {})}
    >
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
              <StarPrice amount={value} />
            </button>
          ))}
        </div>
        <Field
          label="Своя сумма"
          icon="stars_currency"
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
          {amount !== null ? <StarPrice amount={amount} /> : null}
        </Button>
        <Field
          label="Код"
          value={code}
          chevron={false}
          onChange={setCode}
        />
        <Button
          variant="secondary"
          disabled={code.trim() === ""}
          loading={redeem.isPending}
          onClick={() => {
            setNotice("");
            redeem.mutate();
          }}
        >
          Активировать
        </Button>
        {notice !== "" ? <p className={styles.notice}>{notice}</p> : null}
        <Button
          variant="secondary"
          onClick={() => {
            onClose();
            void navigate("/referral");
          }}
        >
          Пригласить друга и получить 20 звёзд
        </Button>
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
    </Dialog>
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
