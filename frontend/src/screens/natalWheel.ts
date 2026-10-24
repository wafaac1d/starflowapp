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

export type NatalGrid = {
  bodies: WheelBody[];
  cusps: number[];
  aspects: WheelAspect[];
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
  return {
    bodies,
    cusps: hasCusps ? cusps : [],
    aspects: aspectsBetween(bodies),
  };
}

function fixtureGrid(): NatalGrid {
  const bodies = natalRows.map((row) => ({
    id: row.id,
    longitude: eclipticLongitude(row.sign, row.degree),
  }));
  const ascendant = bodies.find((body) => body.id === "asc");
  return {
    bodies,
    cusps: equalCusps(ascendant?.longitude ?? 0),
    aspects: aspectsBetween(bodies),
  };
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
