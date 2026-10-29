import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type TouchEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";

import { getNotifications, saveNotifications, type NoticePrefs } from "../api/client";
import { queryKeys } from "../api/keys";
import { Icon } from "../shared/ui/Icon/Icon";
import { Screen } from "../shared/ui/Screen/Screen";
import { Toggle } from "../shared/ui/Toggle/Toggle";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./AffirmationsScreen.module.css";

export type CategoryId = "for_you" | "confidence" | "calm";

export type Affirmation = {
  id: string;
  category: CategoryId;
  text: string;
  bgImage: string;
};

const CATEGORIES: readonly { id: CategoryId; label: string }[] = [
  { id: "for_you", label: "Для вас" },
  { id: "confidence", label: "Уверенность" },
  { id: "calm", label: "Спокойствие" },
] as const;

export const AFFIRMATIONS: Record<CategoryId, Affirmation[]> = {
  for_you: [
    {
      id: "for_you_1",
      category: "for_you",
      text: "«Я доверяю себе\nи выбираю свой ритм.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
    {
      id: "for_you_2",
      category: "for_you",
      text: "«Каждый мой шаг приближает\nменя к гармонии и ясности.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_02.png",
    },
    {
      id: "for_you_3",
      category: "for_you",
      text: "«Я открываюсь новому дню\nс лёгкостью и благодарностью.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_03.png",
    },
  ],
  confidence: [
    {
      id: "confidence_1",
      category: "confidence",
      text: "«Во мне есть всё необходимое,\nчтобы справиться с любыми задачами.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
    {
      id: "confidence_2",
      category: "confidence",
      text: "«Моя внутренняя сила растёт\nс каждым осознанным решением.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_02.png",
    },
    {
      id: "confidence_3",
      category: "confidence",
      text: "«Я верю в свои возможности\nи смело иду вперёд.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_03.png",
    },
  ],
  calm: [
    {
      id: "calm_1",
      category: "calm",
      text: "«Я отпускаю спешку\nи нахожу покой в настоящем моменте.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_01.png",
    },
    {
      id: "calm_2",
      category: "calm",
      text: "«Тишина внутри меня\nсильнее любой внешней суеты.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_02.png",
    },
    {
      id: "calm_3",
      category: "calm",
      text: "«Моё дыхание ровное,\nа мысли ясные и безмятежные.»",
      bgImage: "/affirmations/affirmation_backgrounds/affirmation_background_03.png",
    },
  ],
};

const FAVORITES_KEY = "starflow-affirmation-favorites";
const REMINDER_KEY = "starflow-affirmations-reminder";

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return new Set(parsed.filter((item): item is string => typeof item === "string"));
      }
    }
  } catch {
    // ignore
  }
  return new Set();
}

function saveFavorites(favorites: Set<string>): void {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(Array.from(favorites)));
  } catch {
    // ignore
  }
}

function loadReminderSetting(): boolean {
  try {
    const raw = localStorage.getItem(REMINDER_KEY);
    if (raw !== null) {
      return raw === "true";
    }
  } catch {
    // ignore
  }
  return true;
}

export function AffirmationsScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [category, setCategory] = useState<CategoryId>("for_you");
  const [index, setIndex] = useState(0);
  const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites());
  const [reminder, setReminder] = useState<boolean>(() => loadReminderSetting());

  // Backend notification integration
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

  const cards = AFFIRMATIONS[category];
  const currentCard = cards[index % cards.length] ?? cards[0]!;
  const isSaved = favorites.has(currentCard.id);

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
  const toggleFavorite = () => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(currentCard.id)) {
        next.delete(currentCard.id);
      } else {
        next.add(currentCard.id);
      }
      saveFavorites(next);
      return next;
    });
  };

  // Share action
  const handleShare = async () => {
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
    setReminder(checked);
    try {
      localStorage.setItem(REMINDER_KEY, String(checked));
    } catch {
      // ignore
    }
    // Point of integration with backend notification preferences
    if (notices.data) {
      saveNotices.mutate({
        ...notices.data,
        day: checked,
      });
    }
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
    if (touchStart === null || touchStartY === null) {
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
        <div
          className={styles.cardWrapper}
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
          role="region"
          aria-label="Карточка аффирмации"
        >
          <div
            className={styles.card}
            style={{ backgroundImage: `url("${currentCard.bgImage}")` }}
          >
            {/* Декоративная векторная орбита со звёздами */}
            <svg
              className={styles.cardOrbit}
              viewBox="0 0 340 220"
              fill="none"
              aria-hidden="true"
            >
              <ellipse
                cx="170"
                cy="110"
                rx="150"
                ry="88"
                stroke="rgba(142, 148, 234, 0.28)"
                strokeWidth="1.2"
              />
              {/* Верхняя четырёхлучевая звезда */}
              <path
                d="M 170 16 Q 170 22 176 22 Q 170 22 170 28 Q 170 22 164 22 Q 170 22 170 16 Z"
                fill="#8E94EA"
                opacity="0.85"
              />
              {/* Нижняя четырёхлучевая звезда */}
              <path
                d="M 170 192 Q 170 198 176 198 Q 170 198 170 204 Q 170 198 164 198 Q 170 198 170 192 Z"
                fill="#8E94EA"
                opacity="0.85"
              />
            </svg>
            <p className={styles.cardText}>{currentCard.text}</p>
          </div>
        </div>

        {/* 4. Индикатор страниц */}
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

        {/* 5. Дополнительные действия: Сохранить и Поделиться */}
        <div className={styles.actionRow}>
          <button
            type="button"
            className={isSaved ? styles.actionBtnSaved : styles.actionBtn}
            onClick={toggleFavorite}
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

        {/* 6. Основная кнопка: Другая аффирмация */}
        <button
          type="button"
          className={styles.primaryBtn}
          onClick={nextAffirmation}
          aria-label="Показать другую аффирмацию"
        >
          <Icon name="refresh" size={20} />
          <span>Другая аффирмация</span>
        </button>

        {/* 7. Настройка напоминаний */}
        <div className={styles.reminderCard}>
          <Toggle
            label="Напоминать каждый день"
            checked={reminder}
            onChange={handleReminderChange}
          />
        </div>
      </div>
    </Screen>
  );
}