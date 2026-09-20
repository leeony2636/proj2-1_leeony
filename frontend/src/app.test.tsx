import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("escape room routes", () => { it("renders customer route", () => { render(<MemoryRouter initialEntries={["/customer"]}><App /></MemoryRouter>); expect(screen.getByText("힌트가 필요할 때 질문하세요")).toBeTruthy(); }); it("renders game master route", () => { render(<MemoryRouter initialEntries={["/game-master"]}><App /></MemoryRouter>); expect(screen.getByText("게임 진행 상태")).toBeTruthy(); }); });
