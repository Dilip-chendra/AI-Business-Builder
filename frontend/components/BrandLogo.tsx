type BrandLogoProps = {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  compactText?: boolean;
  textTone?: "light" | "dark";
  className?: string;
};

const LOGO_SRC = "/brand/abb-logo.png";

const sizeMap = {
  sm: { box: 34, width: 48, text: 13, sub: 10 },
  md: { box: 42, width: 62, text: 15, sub: 11 },
  lg: { box: 56, width: 84, text: 18, sub: 12 },
};

export function BrandLogo({
  size = "md",
  showText = true,
  compactText = false,
  textTone = "dark",
  className,
}: BrandLogoProps) {
  const dims = sizeMap[size];
  const primary = textTone === "light" ? "#fff" : "#0f172a";
  const secondary = textTone === "light" ? "rgba(255,255,255,0.55)" : "#64748b";

  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: size === "sm" ? 8 : 10,
        minWidth: 0,
      }}
    >
      <span
        style={{
          width: dims.box,
          height: dims.box,
          borderRadius: size === "lg" ? 16 : 12,
          background: "#030712",
          border: "1px solid rgba(255,255,255,0.12)",
          boxShadow: "0 10px 28px rgba(37,99,235,0.22)",
          overflow: "hidden",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <img
          src={LOGO_SRC}
          alt="AI Business Builder"
          width={dims.width}
          height={dims.width}
          style={{
            width: dims.width,
            height: dims.width,
            maxWidth: "none",
            objectFit: "cover",
            display: "block",
          }}
        />
      </span>
      {showText && (
        <span style={{ display: "inline-flex", flexDirection: "column", minWidth: 0, lineHeight: 1.1 }}>
          <span
            style={{
              color: primary,
              fontWeight: 800,
              fontSize: dims.text,
              letterSpacing: 0,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {compactText ? "ABB" : "AI Business Builder"}
          </span>
          {!compactText && (
            <span
              style={{
                color: secondary,
                fontSize: dims.sub,
                fontWeight: 650,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              Autonomous operating system
            </span>
          )}
        </span>
      )}
    </span>
  );
}

