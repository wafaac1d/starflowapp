type IconProps = {
  name: "chart" | "settings" | "premium" | "terms" | "help" | "support" | "person";
};

export function Icon({ name }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths(name)}
    </svg>
  );
}

function paths(name: IconProps["name"]) {
  if (name === "chart") {
    return (
      <>
        <circle cx="12" cy="12" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6.1 6.1l1.6 1.6M16.3 16.3l1.6 1.6M17.9 6.1l-1.6 1.6M7.7 16.3l-1.6 1.6"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </>
    );
  }
  if (name === "settings") {
    return (
      <>
        <path
          d="M4 8h16M4 16h16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="9" cy="8" r="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="15" cy="16" r="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </>
    );
  }
  if (name === "premium") {
    return (
      <path
        d="M12 4.5 14.2 9l5 .7-3.6 3.5.9 5L12 16.2 7.5 18.2l.9-5L4.8 9.7 9.8 9 12 4.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    );
  }
  if (name === "terms") {
    return (
      <path
        d="M7 4.5h7l4 4V19.5H7v-15Z M14 4.5V9h4 M9.5 13h5 M9.5 16h5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    );
  }
  if (name === "help") {
    return (
      <path
        d="M12 17.5h.01M9.2 9.2a2.8 2.8 0 1 1 4.3 2.4c-.8.5-1.5 1-1.5 2.1v.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    );
  }
  if (name === "support") {
    return (
      <path
        d="M5 7.5h14v8H8l-3 2.5v-10.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    );
  }
  return (
    <>
      <circle cx="12" cy="9" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M6.5 19c1.1-2.4 3-3.5 5.5-3.5s4.4 1.1 5.5 3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </>
  );
}
