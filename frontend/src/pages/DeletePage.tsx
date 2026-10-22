import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { deleteProfile, openSession } from "../api/client";
import { BackHome, Button } from "../components/ui/controls";
import { text } from "../resources";
import { readWebApp } from "../telegram";

type DeletePageProps = {
  fetchImpl?: typeof fetch;
};

export function DeletePage({ fetchImpl }: DeletePageProps) {
  const client = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const remove = useMutation({
    mutationFn: async () => {
      await deleteProfile(fetchImpl);
      const webApp = readWebApp();
      if (webApp === null) {
        return null;
      }
      return openSession(webApp.initData, fetchImpl);
    },
    onSuccess: (next) => {
      if (next !== null) {
        client.setQueryData(["session"], next);
      }
    },
  });
  return (
    <main className="shell">
      <h1>{text("ui.delete.title")}</h1>
      <p className="lead">{text("ui.delete.lead")}</p>
      <p>{text("ui.delete.kept")}</p>
      <p>{text("ui.delete.policy")}</p>
      <label className="consent-row">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(event) => {
            setConfirmed(event.target.checked);
          }}
        />
        <span>{text("ui.delete.confirm")}</span>
      </label>
      <Button
        tone="danger"
        label={text("ui.profile.delete_confirm")}
        disabled={!confirmed || remove.isPending}
        onClick={() => {
          void remove.mutateAsync();
        }}
      />
      <BackHome />
    </main>
  );
}
