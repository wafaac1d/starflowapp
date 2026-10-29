import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { createSupportTicket, type SupportTicket } from "../api/client";
import { Button } from "../shared/ui/Button/Button";
import { Screen } from "../shared/ui/Screen/Screen";
import { TopBar } from "../shared/ui/TopBar/TopBar";
import styles from "./SupportScreen.module.css";

const TOPICS = [
  { id: "question", title: "Вопрос" },
  { id: "payment", title: "Оплата" },
  { id: "bug", title: "Ошибка" },
  { id: "feature", title: "Предложение" },
  { id: "other", title: "Другое" },
] as const;

export function SupportScreen() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState<string>("question");
  const [message, setMessage] = useState("");
  const [sentTicket, setSentTicket] = useState<SupportTicket | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const selectedTopic = TOPICS.find((t) => t.id === topic)?.title ?? "Вопрос";

  const submit = useMutation({
    mutationFn: () => createSupportTicket(selectedTopic, message.trim()),
    onSuccess: (ticket) => {
      setSentTicket(ticket);
      setMessage("");
      setErrorMsg("");
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : "Не удалось отправить обращение");
    },
  });

  const isValid = message.trim().length >= 5 && message.trim().length <= 2000;

  const handleSubmit = () => {
    if (!isValid || submit.isPending) {
      return;
    }
    setErrorMsg("");
    submit.mutate();
  };

  const handleReset = () => {
    setSentTicket(null);
    setMessage("");
    setErrorMsg("");
  };

  return (
    <Screen tab="profile">
      <TopBar
        title="Поддержка"
        back
        onBack={() => {
          void navigate(-1);
        }}
      />
      <div className={styles.container}>
        <p className={styles.subtitle}>Служба поддержки и обратная связь</p>

        {sentTicket !== null ? (
          <article className={styles.successCard} role="status" aria-label="Обращение отправлено">
            <h2 className={styles.successTitle}>Обращение отправлено</h2>
            <p className={styles.successText}>
              Мы получили ваше сообщение по теме «{sentTicket.subject}» и ответим вам в ближайшее время.
            </p>
            <div className={styles.successButtons}>
              <Button onClick={handleReset}>
                Отправить ещё одно
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  void navigate("/profile");
                }}
              >
                Вернуться в профиль
              </Button>
            </div>
          </article>
        ) : (
          <>
            <div className={styles.topicsGroup}>
              <p className={styles.topicsLabel}>Тема обращения</p>
              <div className={styles.topics} role="group" aria-label="Тема обращения">
                {TOPICS.map((t) => {
                  const active = topic === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      className={active ? styles.topicBtnActive : styles.topicBtn}
                      aria-pressed={active}
                      onClick={() => setTopic(t.id)}
                    >
                      {t.title}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className={styles.field}>
              <label htmlFor="support-message" className={styles.fieldLabel}>
                Ваше сообщение
              </label>
              <textarea
                id="support-message"
                className={styles.textarea}
                value={message}
                maxLength={2000}
                placeholder="Опишите ваш вопрос, сложность с оплатой или предложение..."
                onChange={(e) => setMessage(e.target.value)}
              />
              <p className={styles.counter}>{message.trim().length} / 2000</p>
            </div>

            {errorMsg !== "" ? (
              <p className={styles.error} role="alert">
                {errorMsg}
              </p>
            ) : null}

            <Button
              loading={submit.isPending}
              disabled={!isValid || submit.isPending}
              onClick={handleSubmit}
            >
              Отправить обращение
            </Button>
          </>
        )}
      </div>
    </Screen>
  );
}