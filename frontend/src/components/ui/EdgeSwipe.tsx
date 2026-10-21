import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router";

import { backTarget, isEdgeBackSwipe, rememberNavigation, type HistoryMark } from "../../edgeSwipe";

export function EdgeSwipe() {
  const navigate = useNavigate();
  const location = useLocation();
  const action = useNavigationType();
  const stack = useRef<HistoryMark[]>([]);
  const [drag, setDrag] = useState(0);

  useEffect(() => {
    stack.current = rememberNavigation(stack.current, location.key, location.pathname, action);
  }, [action, location.key, location.pathname]);

  useEffect(() => {
    let startX = 0;
    let startY = 0;
    let pointerId = -1;
    let tracking = false;

    const end = () => {
      tracking = false;
      pointerId = -1;
      setDrag(0);
    };

    const onDown = (event: PointerEvent) => {
      if (tracking || event.clientX > 28) {
        return;
      }
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      const target = event.target;
      if (target instanceof Element && target.closest("input, textarea, select") !== null) {
        return;
      }
      startX = event.clientX;
      startY = event.clientY;
      pointerId = event.pointerId;
      tracking = true;
    };

    const onMove = (event: PointerEvent) => {
      if (!tracking || event.pointerId !== pointerId) {
        return;
      }
      const dx = event.clientX - startX;
      const dy = event.clientY - startY;
      if (dy < -48 && Math.abs(dy) > dx) {
        end();
        return;
      }
      if (dx > 12 && dx > Math.abs(dy)) {
        setDrag(Math.min(dx, 96));
      }
    };

    const onUp = (event: PointerEvent) => {
      if (!tracking || event.pointerId !== pointerId) {
        return;
      }
      const dx = event.clientX - startX;
      const dy = event.clientY - startY;
      end();
      if (!isEdgeBackSwipe(startX, dx, dy)) {
        return;
      }
      const target = backTarget(stack.current.length, location.pathname);
      if (target === "history") {
        void navigate(-1);
      } else if (target === "home") {
        void navigate("/");
      }
    };

    window.addEventListener("pointerdown", onDown);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [location.pathname, navigate]);

  return (
    <div
      className="edge-swipe"
      data-active={drag > 0}
      style={{ width: drag }}
      aria-hidden="true"
    />
  );
}
