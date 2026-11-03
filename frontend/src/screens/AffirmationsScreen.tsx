import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type TouchEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import {
  ApiRequestError,
  deleteAffirmationKeep,
  getAffirmationKeeps,
  getAffirmations,
  getAffirmationsStatus,
  getNotifications,
  saveAffirmationKeep,
  saveNotifications,
  spendStars,
  type AffirmationCard,
  type NoticePrefs,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { Button } from "../shared/ui/Button/Button";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { StarLink } from "../shared/ui/StarLink/StarLink";
import { StarPrice } from "../shared/ui/StarPrice/StarPrice";
import { Toggle } from "../shared/ui/Toggle/Toggle";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import { holdStarBalance, writeStarBalance } from "../starBalance";
import { AFFIRMATION_STARS } from "../stars";
import { TopUpDialog } from "./TopUpDialog";
import styles from "./AffirmationsScreen.module.css";

export type CategoryId = "for_you" | "confidence" | "calm";

const CATEGORIES: readonly { id: CategoryId; label: string }[] = [
  { id: "for_you", label: "Для вас" },
  { id: "confidence", label: "Уверенность" },
  { id: "calm", label: "Спокойствие" },
] as const;

function isCategory(value: string | null | undefined): value is CategoryId {
  return value === "for_you" || value === "confidence" || value === "calm";
}

function CardOrbit() {
  return (
    <svg className={styles.cardOrbit} viewBox="0 0 340 220" fill="none" aria-hidden="true">
      <ellipse className={styles.orbit} cx="170" cy="110" rx="150" ry="88" />
      <path
        className={styles.orbitStar}
        d="M 170 16 Q 170 22 176 22 Q 170 22 170 28 Q 170 22 164 22 Q 170 22 170 16 Z"
      />
      <path
        className={styles.orbitStar}
        d="M 170 192 Q 170 198 176 198 Q 170 198 170 204 Q 170 198 164 198 Q 170 198 170 192 Z"
      />
    </svg>
  );
}

export function AffirmationsScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [topUp, setTopUp] = useState(false);

  const [category, setCategory] = useState<CategoryId | null>(null);
  const [index, setIndex] = useState(0);

  const statusQuery = useQuery({
    queryKey: queryKeys.affirmationsStatus,
    queryFn: () => getAffirmationsStatus(),
  });
  useEffect(() => {
    const chosen = statusQuery.data?.chosen_category;
    if (category === null && isCategory(chosen)) {
      setCategory(chosen);
    }
  }, [category, statusQuery.data]);
  const affirmationsQuery = useQuery({
    queryKey: queryKeys.affirmations(category ?? "none"),
    queryFn: () => {
      if (category === null) {
        return Promise.reject(new Error("category"));
      }
      return getAffirmations(category);
    },
    enabled: category !== null,
  });
  const keeps = useQuery({
    queryKey: queryKeys.affirmationKeeps,
    queryFn: () => getAffirmationKeeps(),
  });

  const access = affirmationsQuery.data?.access ?? "preview";
  const isLocked = category !== null && access === "locked";
  const price = affirmationsQuery.data?.price ?? AFFIRMATION_STARS;
  const freeChosenLabel = affirmationsQuery.data?.free_chosen_label;
  const currentCategoryLabel = CATEGORIES.find((c) => c.id === category)?.label ?? "";

  const notices = useQuery({
    queryKey: queryKeys.notifications,
    queryFn: () => getNotifications(),
  });
  const saveNotices = useMutation({
    mutationFn: (next: NoticePrefs) => saveNotifications(next),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.notifications, saved);
    },
  });

  const cards = useMemo(() => affirmationsQuery.data?.cards ?? [], [affirmationsQuery.data]);
  const currentCard: AffirmationCard | undefined =
    cards.length > 0 ? cards[index % cards.length] : undefined;
  const isSaved = currentCard
    ? keeps.data?.some((item) => item.card_id === currentCard.id) === true
    : false;

  const buy = useMutation({
    mutationFn: () => {
      if (category === null) {
        return Promise.reject(new Error("no category"));
      }
      return spendStars({ feature: "affirmation", category });
    },
    onMutate: () => holdStarBalance(queryClient, price),
    onSuccess: async (ticket, _variables, restore) => {
      if (ticket.charged) {
        writeStarBalance(queryClient, ticket.balance);
      } else {
        restore?.();
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.affirmations(category ?? "none") });
      await queryClient.invalidateQueries({ queryKey: queryKeys.affirmationsStatus });
    },
    onError: (error, _variables, restore) => {
      restore?.();
      if (error instanceof ApiRequestError && error.status === 402) {
        setTopUp(true);
      }
    },
  });

  // Switch category
  const selectCategory = (newCat: CategoryId) => {
    if (newCat !== category) {
      setCategory(newCat);
      setIndex(0);
    }
  };

  // Next affirmation button
  const nextAffirmation = () => {
    if (cards.length > 1) {
      setIndex((prev) => (prev + 1) % cards.length);
    }
  };

  // Toggle favorite
  const keepCard = useMutation({
    mutationFn: async (card: AffirmationCard) => {
      if (keeps.data?.some((item) => item.card_id === card.id)) {
        await deleteAffirmationKeep(card.id);
        return;
      }
      await saveAffirmationKeep({ card_id: card.id, text: card.text, category: card.category });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.affirmationKeeps });
      await queryClient.invalidateQueries({ queryKey: queryKeys.favorites });
    },
  });

  // Share action
  const handleShare = async () => {
    if (!currentCard) {
      return;
    }
    const textToShare = currentCard.text.replace(/«|»/g, "").trim();
    if (navigator.share) {
      try {
        await navigator.share({
          title: "Аффирмация дня",
          text: textToShare,
        });
      } catch {
        // user cancelled share
      }
    } else if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(textToShare);
      } catch {
        // ignore clipboard error
      }
    }
  };

  // Reminder toggle
  const handleReminderChange = (checked: boolean) => {
    if (notices.data === undefined) {
      return;
    }
    saveNotices.mutate({
      ...notices.data,
      affirmation: checked,
    });
  };

  // Horizontal swipe gestures
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);

  const onTouchStart = (e: TouchEvent<HTMLDivElement>) => {
    const firstTouch = e.touches[0];
    if (firstTouch) {
      setTouchStart(firstTouch.clientX);
      setTouchStartY(firstTouch.clientY);
    }
  };

  const onTouchEnd = (e: TouchEvent<HTMLDivElement>) => {
    if (touchStart === null || touchStartY === null || isLocked || cards.length === 0) {
      return;
    }
    const endTouch = e.changedTouches[0];
    if (endTouch) {
      const diffX = touchStart - endTouch.clientX;
      const diffY = touchStartY - endTouch.clientY;
      if (Math.abs(diffX) > 40 && Math.abs(diffX) > Math.abs(diffY)) {
        if (diffX > 0) {
          // Swipe left -> next
          setIndex((prev) => (prev + 1) % cards.length);
        } else {
          // Swipe right -> prev
          setIndex((prev) => (prev - 1 + cards.length) % cards.length);
        }
      }
    }
    setTouchStart(null);
    setTouchStartY(null);
  };

  return (
    <Screen tab="today">
      <TopBar
        title="Аффирмации"
        back
        onBack={() => {
          void navigate("/");
        }}
      />
      <div className={styles.container}>
        <p className={styles.subtitle}>Мягкая настройка на день</p>

        {/* 2. Переключатель категорий */}
        <div className={styles.categories} role="group" aria-label="Категории аффирмаций">
          {CATEGORIES.map((cat) => {
            const active = category === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                className={active ? styles.categoryBtnActive : styles.categoryBtn}
                aria-pressed={active}
                onClick={() => selectCategory(cat.id)}
              >
                {cat.label}
              </button>
            );
          })}
        </div>

        {/* 3. Карточка аффирмации со свайпом */}
        {category === null ? (
          <p className={styles.subtitle}>Выберите категорию</p>
        ) : affirmationsQuery.isPending ? (
          <StarLink />
        ) : affirmationsQuery.isError ? (
          <div>
            <p className={styles.subtitle}>Не удалось открыть аффирмации</p>
            <Button
              onClick={() => {
                void affirmationsQuery.refetch();
              }}
            >
              Повторить
            </Button>
          </div>
        ) : isLocked ? (
          <div className={styles.cardWrapper} role="region" aria-label="Карточка аффирмации">
            <div className={styles.card}>
              <CardOrbit />
              <div className={styles.lockedCopy}>
                <h2 className={styles.lockedTitle}>Категория недоступна бесплатно</h2>
                <p className={styles.lockedText}>
                  {freeChosenLabel
                    ? `Бесплатно в день доступна только одна категория. Сегодня вы уже выбрали «${freeChosenLabel}».`
                    : "Бесплатно в день доступна только одна категория."}
                </p>
              </div>
            </div>
          </div>
        ) : currentCard ? (
          <div
            className={styles.cardWrapper}
            onTouchStart={onTouchStart}
            onTouchEnd={onTouchEnd}
            role="region"
            aria-label="Карточка аффирмации"
          >
            <div
              className={styles.card}
              style={
                currentCard.bg_image
                  ? { backgroundImage: `url("${currentCard.bg_image}")` }
                  : undefined
              }
            >
              <CardOrbit />
              <p className={styles.cardText}>{currentCard.text}</p>
            </div>
          </div>
        ) : null}

        {/* 4. Индикатор страниц */}
        {!isLocked && cards.length > 1 ? (
          <div className={styles.dots} role="tablist" aria-label="Индикатор страниц">
            {cards.map((card, i) => (
              <button
                key={card.id}
                type="button"
                className={i === (index % cards.length) ? styles.dotActive : styles.dot}
                aria-label={`Аффирмация ${i + 1}`}
                aria-selected={i === (index % cards.length)}
                onClick={() => setIndex(i)}
              />
            ))}
          </div>
        ) : null}

        {/* 5. Дополнительные действия: Сохранить и Поделиться */}
        {!isLocked && currentCard ? (
          <div className={styles.actionRow}>
            <button
              type="button"
              className={isSaved ? styles.actionBtnSaved : styles.actionBtn}
              onClick={() => {
                keepCard.mutate(currentCard);
              }}
              aria-label={isSaved ? "Удалить из сохранённых" : "Сохранить аффирмацию"}
            >
              <Icon name={isSaved ? "heart_filled" : "heart"} size={20} />
              <span>{isSaved ? "Сохранено" : "Сохранить"}</span>
            </button>
            <button
              type="button"
              className={styles.actionBtn}
              onClick={handleShare}
              aria-label="Поделиться аффирмацией"
            >
              <Icon name="share" size={20} />
              <span>Поделиться</span>
            </button>
          </div>
        ) : null}

        {/* 6. Основная кнопка: Другая аффирмация */}
        {!isLocked && cards.length > 1 ? (
          <button
            type="button"
            className={styles.primaryBtn}
            onClick={nextAffirmation}
            aria-label="Показать другую аффирмацию"
          >
            <Icon name="refresh" size={20} />
            <span>Другая аффирмация</span>
          </button>
        ) : null}

        {/* Баннер разблокировки за звёзды */}
        {isLocked ? (
          <section className={styles.affirmationOffer}>
            <p>
              Полный доступ к аффирмациям категории «{currentCategoryLabel}» стоит{" "}
              <StarPrice amount={price} /> звёзд. С Premium они без ограничений.
            </p>
            <Button
              loading={buy.isPending}
              onClick={() => {
                buy.mutate();
              }}
            >
              Открыть за <StarPrice amount={price} />
            </Button>
          </section>
        ) : category !== null && access === "preview" && price > 0 && !affirmationsQuery.isError ? (
          <section className={styles.affirmationOffer}>
            <p>
              Одна аффирмация в день бесплатно. Откройте все аффирмации этой категории за{" "}
              <StarPrice amount={price} /> звёзд или с Premium.
            </p>
            <Button
              loading={buy.isPending}
              onClick={() => {
                buy.mutate();
              }}
            >
              Открыть за <StarPrice amount={price} />
            </Button>
          </section>
        ) : null}

        {/* 7. Настройка напоминаний */}
        {notices.data ? (
          <div className={styles.reminderCard}>
            <Toggle
              label="Напоминать каждый день"
              checked={notices.data.affirmation}
              onChange={handleReminderChange}
            />
          </div>
        ) : null}

        {topUp ? <TopUpDialog balance={null} onClose={() => setTopUp(false)} /> : null}
      </div>
    </Screen>
  );
}