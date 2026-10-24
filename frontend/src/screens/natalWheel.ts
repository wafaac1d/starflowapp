import { natalRows } from "../api/fixtures";

const SIGN_INDEX: Record<string, number> = {
  овен: 0,
  телец: 1,
  близнецы: 2,
  рак: 3,
  лев: 4,
  дева: 5,
  весы: 6,
  скорпион: 7,
  стрелец: 8,
  козерог: 9,
  водолей: 10,
  рыбы: 11,
};

const ASPECTS = [
  { name: "sextile", angle: 60, orb: 4, kind: "soft" },
  { name: "square", angle: 90, orb: 6, kind: "hard" },
  { name: "trine", angle: 120, orb: 6, kind: "soft" },
  { name: "opposition", angle: 180, orb: 8, kind: "hard" },
] as const;

export type WheelBody = {
  id: string;
  longitude: number;
};

export type WheelAspect = {
  id: string;
  from: string;
  to: string;
  kind: "soft" | "hard";
};

export type WheelLink = {
  id: string;
  start: number;
  end: number;
};

export type NatalGrid = {
  bodies: WheelBody[];
  cusps: number[];
  aspects: WheelAspect[];
  figure: WheelLink[];
};

export function eclipticLongitude(sign: string, degree: string): number {
  const index = SIGN_INDEX[sign.toLocaleLowerCase("ru")];
  const match = /^(\d+)°(\d+)′$/.exec(degree);
  const degrees = match?.[1];
  const minutes = match?.[2];
  if (index === undefined || degrees === undefined || minutes === undefined) {
    throw new Error("natal placement is incomplete");
  }
  return index * 30 + Number(degrees) + Number(minutes) / 60;
}

export function wheelPoint(longitude: number, radius: number): { x: number; y: number } {
  const rad = (longitude * Math.PI) / 180;
  return {
    x: 50 + radius * Math.sin(rad),
    y: 50 - radius * Math.cos(rad),
  };
}

export function equalCusps(ascendant: number): number[] {
  return Array.from({ length: 12 }, (_, index) => (ascendant + index * 30) % 360);
}

export function natalGrid(chart: {
  planets: { name: string; longitude: number }[];
  houseCusps: number[] | null;
} | undefined): NatalGrid {
  const cusps = chart?.houseCusps;
  const hasCusps = cusps !== undefined && cusps !== null && cusps.length === 12;
  const planets = chart?.planets ?? [];
  if (planets.length === 0 && !hasCusps) {
    return fixtureGrid();
  }
  const bodies = planets.map((planet) => ({ id: planet.name, longitude: planet.longitude }));
  const houseCusps = hasCusps ? cusps : [];
  return {
    bodies,
    cusps: houseCusps,
    aspects: aspectsBetween(bodies),
    figure: figureOf([...houseCusps, ...bodies.map((body) => body.longitude)]),
  };
}

function fixtureGrid(): NatalGrid {
  const bodies = natalRows.map((row) => ({
    id: row.id,
    longitude: eclipticLongitude(row.sign, row.degree),
  }));
  const ascendant = bodies.find((body) => body.id === "asc");
  const cusps = equalCusps(ascendant?.longitude ?? 0);
  return {
    bodies,
    cusps,
    aspects: aspectsBetween(bodies),
    figure: figureOf([...cusps, ...bodies.map((body) => body.longitude)]),
  };
}

function figureOf(longitudes: number[]): WheelLink[] {
  const unique: number[] = [];
  for (const value of [...longitudes].sort((left, right) => left - right)) {
    const previous = unique[unique.length - 1];
    if (previous === undefined || Math.abs(value - previous) > 0.05) {
      unique.push(value);
    }
  }
  const count = unique.length;
  if (count < 3) {
    return [];
  }
  const links: WheelLink[] = [];
  const seen = new Set<string>();
  const add = (step: number) => {
    for (let index = 0; index < count; index += 1) {
      const other = (index + step) % count;
      const left = Math.min(index, other);
      const right = Math.max(index, other);
      const key = `${left}-${right}`;
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const start = unique[left];
      const end = unique[right];
      if (start === undefined || end === undefined) {
        continue;
      }
      links.push({ id: `figure-${key}`, start, end });
    }
  };
  add(1);
  if (count > 4) {
    add(Math.min(5, Math.floor(count / 2)));
  }
  return links;
}

function aspectsBetween(bodies: WheelBody[]): WheelAspect[] {
  const found: WheelAspect[] = [];
  for (let left = 0; left < bodies.length; left += 1) {
    const first = bodies[left];
    if (first === undefined) {
      continue;
    }
    for (let right = left + 1; right < bodies.length; right += 1) {
      const second = bodies[right];
      if (second === undefined) {
        continue;
      }
      const hit = aspectKind(first.longitude, second.longitude);
      if (hit === null) {
        continue;
      }
      found.push({
        id: `${first.id}-${second.id}-${hit.name}`,
        from: first.id,
        to: second.id,
        kind: hit.kind,
      });
    }
  }
  return found;
}

function aspectKind(left: number, right: number): { name: string; kind: "soft" | "hard" } | null {
  let separation = Math.abs(left - right) % 360;
  if (separation > 180) {
    separation = 360 - separation;
  }
  for (const aspect of ASPECTS) {
    if (Math.abs(separation - aspect.angle) <= aspect.orb) {
      return { name: aspect.name, kind: aspect.kind };
    }
  }
  return null;
}
