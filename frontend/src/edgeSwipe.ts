export type HistoryMark = {
  key: string;
  path: string;
};

export type NavigationAction = "POP" | "PUSH" | "REPLACE";

const EDGE_PX = 28;
const TRAVEL_PX = 80;

export function rememberNavigation(
  stack: HistoryMark[],
  key: string,
  path: string,
  action: NavigationAction,
): HistoryMark[] {
  if (path === "/" && action !== "POP") {
    return [{ key, path }];
  }
  const index = stack.findIndex((entry) => entry.key === key);
  if (index >= 0) {
    return stack.slice(0, index + 1);
  }
  return [...stack, { key, path }];
}

export function backTarget(stackLength: number, pathname: string): "history" | "home" | "stay" {
  if (stackLength > 1) {
    return "history";
  }
  if (pathname !== "/") {
    return "home";
  }
  return "stay";
}

export function isEdgeBackSwipe(startX: number, dx: number, dy: number): boolean {
  return startX <= EDGE_PX && dx >= TRAVEL_PX && Math.abs(dy) <= dx * 0.75;
}
