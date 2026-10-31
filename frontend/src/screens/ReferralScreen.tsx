import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getReferral } from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Screen } from "../shared/ui/Screen/Screen";
import { Skeleton } from "../shared/ui/Skeleton/Skeleton";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./ReferralScreen.module.css";

export function ReferralScreen({ fetchImpl = fetch }: { fetchImpl?: typeof fetch }) {
  const [copied, setCopied] = useState(false);
  const referral = useQuery({
    queryKey: queryKeys.referral,
    queryFn: () => getReferral(fetchImpl),
  });

  const data = referral.data;

  const copyLink = async () => {
    if (!data?.link) {
      return;
    }
    try {
      await navigator.clipboard.writeText(data.link);
      setCopied(true);
      setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch {
      // Clipboard fallback
    }
  };

  const shareLink = async () => {
    if (!data?.link) {
      return;
    }
    const shareText = "Присоединяйтесь к StarFlow по моей ссылке и получите 20 звёзд на баланс!";
    if (navigator.share) {
      try {
        await navigator.share({
          title: "StarFlow",
          text: shareText,
          url: data.link,
        });
        return;
      } catch {
        // Fallback to Telegram share
      }
    }
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(data.link)}&text=${encodeURIComponent(shareText)}`;
    if (window.Telegram?.WebApp?.openTelegramLink) {
      window.Telegram.WebApp.openTelegramLink(tgUrl);
    } else {
      window.open(tgUrl, "_blank");
    }
  };

  return (
    <Screen tab="profile">
      <TopBar title="Реферальная программа" back />
      <div className={styles.container}>
        {referral.isPending || data === undefined ? (
          <Skeleton lines={6} />
        ) : (
          <>
            <div className={styles.card}>
              <h2 className={styles.cardTitle}>Приглашайте друзей</h2>
              <p className={styles.cardDesc}>
                Поделитесь вашей ссылкой с друзьями. За каждого, кто зарегистрируется по ней, вы
                получите 20 звёзд, и ваш друг тоже получит 20 звёзд на свой баланс.
              </p>
            </div>

            <div className={styles.statsGrid}>
              <div className={styles.statCard}>
                <span className={styles.statValue}>{data.count}</span>
                <span className={styles.statLabel}>Приглашено друзей</span>
              </div>
              <div className={styles.statCard}>
                <span className={styles.statValue}>
                  <StarPrice amount={data.stars_earned} />
                </span>
                <span className={styles.statLabel}>Заработано звёзд</span>
              </div>
            </div>

            <div className={styles.card}>
              <h3 className={styles.sectionTitle}>Ваша реферальная ссылка</h3>
              <div className={styles.linkBox}>{data.link}</div>
              <div className={styles.actions}>
                <Button fit onClick={copyLink}>
                  {copied ? "Ссылка скопирована" : "Скопировать ссылку"}
                </Button>
                <Button variant="secondary" fit onClick={shareLink}>
                  Поделиться
                </Button>
              </div>
            </div>

            <div className={styles.card}>
              <h3 className={styles.sectionTitle}>Как это работает</h3>
              <ol className={styles.list}>
                <li>Отправьте другу вашу персональную ссылку.</li>
                <li>Друг регистрируется в StarFlow и получает 20 звёзд на баланс.</li>
                <li>Вы получаете 20 звёзд сразу после регистрации друга.</li>
              </ol>
            </div>
          </>
        )}
      </div>
    </Screen>
  );
}
