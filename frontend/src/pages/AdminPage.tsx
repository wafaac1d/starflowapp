import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { getAdminUsers, grantAdminPeriod, type AdminUser } from "../api/client";
import { queryKeys } from "../api/keys";
import { BackHome, Button } from "../components/ui/controls";
import { formatText, text } from "../resources";
import styles from "./AdminPage.module.css";

type AdminPageProps = {
  isAdmin: boolean;
  fetchImpl?: typeof fetch;
};

const INITIAL_DAYS = "7";
const PAGE_SIZE = 10;

export function AdminPage({ isAdmin, fetchImpl = fetch }: AdminPageProps) {
  const [userId, setUserId] = useState("");
  const [days, setDays] = useState(INITIAL_DAYS);
  const [reason, setReason] = useState("");
  const [grantConfirmed, setGrantConfirmed] = useState(false);
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const people = useQuery({
    queryKey: [...queryKeys.adminUsers, page],
    queryFn: () => getAdminUsers(page, fetchImpl, PAGE_SIZE),
    enabled: isAdmin,
  });
  const grant = useMutation({
    mutationFn: () => grantAdminPeriod(userId, Number(days), reason, fetchImpl),
    onSuccess: async () => {
      setUserId("");
      setDays(INITIAL_DAYS);
      setReason("");
      setGrantConfirmed(false);
      await client.refetchQueries({ queryKey: queryKeys.adminUsers });
    },
  });
  if (!isAdmin) {
    return (
      <main className="shell">
        <h1>{text("ui.admin.title")}</h1>
        <p>{text("ui.admin.denied")}</p>
        <BackHome />
      </main>
    );
  }
  const canGrant =
    grantConfirmed && reason.trim() !== "" && userId.trim() !== "" && !grant.isPending;
  return (
    <main className={styles.page}>
      <h1>{text("ui.admin.title")}</h1>
      <p>{text("ui.admin.lead")}</p>
      <h2>{text("ui.admin.people")}</h2>
      <p>{text("ui.admin.people_lead")}</p>
      <UserTable
        rows={people.data?.users ?? []}
        page={page}
        total={people.data?.total ?? 0}
        onPick={setUserId}
        onPage={setPage}
      />
      <h2>{text("ui.admin.grant")}</h2>
      <div className={styles.form}>
      <label className="field">
        <span>{text("ui.admin.grant_user")}</span>
        <input
          className="as-typed"
          value={userId}
          onChange={(event) => {
            setUserId(event.target.value);
          }}
        />
      </label>
      <label className="field">
        <span>{text("ui.admin.grant_days")}</span>
        <input
          value={days}
          inputMode="numeric"
          onChange={(event) => {
            setDays(event.target.value);
          }}
        />
      </label>
      <label className="field">
        <span>{text("ui.admin.reason")}</span>
        <input
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
          }}
        />
      </label>
      <label className="consent-row">
        <input
          type="checkbox"
          checked={grantConfirmed}
          onChange={(event) => {
            setGrantConfirmed(event.target.checked);
          }}
        />
        <span>{text("ui.admin.confirm")}</span>
      </label>
      <Button
        label={text("ui.admin.grant")}
        disabled={!canGrant}
        onClick={() => {
          void grant.mutateAsync();
        }}
      />
      <BackHome />
      </div>
    </main>
  );
}

function UserTable({
  rows,
  page,
  total,
  onPick,
  onPage,
}: {
  rows: AdminUser[];
  page: number;
  total: number;
  onPick: (userId: string) => void;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return (
    <>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{text("ui.admin.col_name")}</th>
              <th scope="col">{text("ui.admin.col_telegram")}</th>
              <th scope="col">{text("ui.admin.col_id")}</th>
              <th scope="col">{text("ui.admin.col_premium")}</th>
              <th scope="col">
                <span className={styles.srOnly}>{text("ui.admin.pick")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((person) => (
              <tr key={person.user_id}>
                <td>{person.display_name ?? text("ui.admin.unnamed")}</td>
                <td>{person.username === null ? "" : `@${person.username}`}</td>
                <td>{person.telegram_id}</td>
                <td>{person.premium ? text("ui.admin.premium_on") : text("ui.admin.premium_off")}</td>
                <td>
                  <Button
                    tone="outline"
                    label={text("ui.admin.pick")}
                    onClick={() => {
                      onPick(person.user_id);
                    }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles.pager}>
        <button
          type="button"
          className={styles.pageButton}
          disabled={page <= 1}
          onClick={() => {
            onPage(page - 1);
          }}
        >
          {text("ui.admin.page_prev")}
        </button>
        <p>{formatText("ui.admin.page_status", { page: String(page), pages: String(pages) })}</p>
        <button
          type="button"
          className={styles.pageButton}
          disabled={page >= pages}
          onClick={() => {
            onPage(page + 1);
          }}
        >
          {text("ui.admin.page_next")}
        </button>
      </div>
    </>
  );
}
