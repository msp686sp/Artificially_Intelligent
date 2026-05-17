import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubScoreRadar } from "../../src/charts/SubScoreRadar";

describe("SubScoreRadar", () => {
  it("renders a single-zip radar wrapped in a ResponsiveContainer", () => {
    render(
      <div style={{ width: 400, height: 400 }}>
        <SubScoreRadar
          series={[
            {
              name: "10025",
              scores: {
                yield_score: 70,
                growth_score: 60,
                stability_score: 80,
                affordability_score: 40,
                risk_score: 30,
              },
            },
          ]}
        />
      </div>,
    );
    expect(screen.getByTestId("subscore-radar")).toBeInTheDocument();
  });

  it("renders multiple overlaid series", () => {
    render(
      <div style={{ width: 400, height: 400 }}>
        <SubScoreRadar
          series={[
            { name: "A", scores: { yield_score: 50 } },
            { name: "B", scores: { yield_score: 70 } },
            { name: "C", scores: { yield_score: 30 } },
          ]}
        />
      </div>,
    );
    expect(screen.getByTestId("subscore-radar")).toBeInTheDocument();
  });

  it("handles missing scores gracefully", () => {
    render(
      <div style={{ width: 400, height: 400 }}>
        <SubScoreRadar series={[{ name: "10025", scores: null }]} />
      </div>,
    );
    expect(screen.getByTestId("subscore-radar")).toBeInTheDocument();
  });
});
