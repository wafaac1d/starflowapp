import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getAdminOverview,
  getAdminUsers,
  grantAdminPeriod,
  refundCharge,
  type AdminOverview,
} from "../api/client";
import { queryKeys } from "../api/keys";
import { BackHome, Button } from "../components/ui/controls";
import { text } from "../resources";

type AdminPageProps = {
  isAdmin: boolean;
  fetchImpl?: typeof fetch;
};

export function AdminPage({ isAdmin, fetchImpl = fetch }: AdminPageProps) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [userId, setUserId] = useState("");
  const [days, setDays] = useState("7");
  const [reason, setReason] = useState("");
  const [charge, setCharge] = useState("");
  const [grantConfirmed, setGrantConfirmed] = useState(false);
  const [refundConfirmed, setRefundConfirmed] = useState(false);
  const client = useQueryClient();
  const overview = useQuery({
    queryKey: ["admin", start, end],
    queryFn: () => getAdminOverview(start, end, fetchImpl),
    enabled: isAdmin,
  });
  const people = useQuery({
    queryKey: queryKeys.adminUsers,
    queryFn: () => getAdminUsers(fetchImpl),
    enabled: isAdmin,
  });
  const grant = useMutation({
    mutationFn: () => grantAdminPeriod(userId, Number(days), reason, fetchImpl),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: queryKeys.adminUsers });
    },
  });
  const refund = useMutation({
    mutationFn: () => refundCharge(charge, reason, fetchImpl),
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
  return (
    <main className="shell">
      <h1>{text("ui.admin.title")}</h1>
      <p className="lead">{text("ui.admin.lead")}</p>
      <label className="field">
        <span>{text("ui.admin.from")}</span>
        <input
          type="date"
          value={start}
          onChange={(event) => {
            setStart(event.target.value);
          }}
        />
      </label>
      <label className="field">
        <span>{text("ui.admin.to")}</span>
        <input
          type="date"
          value={end}
          onChange={(event) => {
            setEnd(event.target.value);
          }}
        />
      </label>
      {overview.data === undefined ? null : <AdminFigures report={overview.data} />}
      <h2>{text("ui.admin.people")}</h2>
      <p className="lead">{text("ui.admin.people_lead")}</p>
      <ul>
        {(people.data ?? []).map((person) => (
          <li key={person.user_id}>
            <p>
              {person.display_name ?? text("ui.admin.unnamed")}
              {person.username !== null ? ` @${person.username}` : ""} · {person.telegram_id} ·{" "}
              {person.premium ? text("ui.admin.premium_on") : text("ui.admin.premium_off")}
            </p>
            <Button
              tone="outline"
              label={text("ui.admin.pick")}
              onClick={() => {
                setUserId(person.user_id);
              }}
            />
          </li>
        ))}
      </ul>
      <h2>{text("ui.admin.grant")}</h2>
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
        disabled={!grantConfirmed || reason.trim() === "" || userId.trim() === ""}
        onClick={() => {
          void grant.mutateAsync();
        }}
      />
      <h2>{text("ui.admin.refund")}</h2>
      <label className="field">
        <span>{text("ui.admin.charge")}</span>
        <input
          className="as-typed"
          value={charge}
          onChange={(event) => {
            setCharge(event.target.value);
          }}
        />
      </label>
      <label className="consent-row">
        <input
          type="checkbox"
          checked={refundConfirmed}
          onChange={(event) => {
            setRefundConfirmed(event.target.checked);
          }}
        />
        <span>{text("ui.admin.confirm")}</span>
      </label>
      <Button
        tone="danger"
        label={text("ui.admin.refund")}
        disabled={!refundConfirmed || reason.trim() === "" || charge.trim() === ""}
        onClick={() => {
          void refund.mutateAsync();
        }}
      />
      <BackHome />
    </main>
  );
}

function AdminFigures({ report }: { report: AdminOverview }) {
  return (
    <section>
      <p>
        {report.start} — {report.end}
      </p>
      <p>
        {report.active_users} / {report.open_accounts}
      </p>
      <p>
        {report.payments} / {report.stars} / {report.refunds}
      </p>
      <p>{report.definitions.active_users}</p>
      <p>{report.definitions.payments}</p>
      <p>{report.definitions.cache}</p>
      <p>
        {report.cache.l1_hits}/{report.cache.l1_misses} l1, {report.cache.l2_hits} l2,{" "}
        {report.cache.process_generations}
      </p>
      <ul>
        {report.feedback.map((item) => (
          <li key={`${item.forecast_type}-${item.prompt_version}`}>
            {item.forecast_type} {item.prompt_version || "—"} {item.count}
          </li>
        ))}
      </ul>
      <p>{report.definitions.feedback}</p>
    </section>
  );
}
