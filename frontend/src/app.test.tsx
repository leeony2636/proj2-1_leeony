import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("escape room routes", () => {
  it("renders customer route", () => {
    render(<MemoryRouter initialEntries={["/customer"]}><App /></MemoryRouter>);
    expect(screen.getByText("도움이 필요할 때 말씀해 주세요")).toBeTruthy();
    // 수정 사유: ANSWER는 서버가 발급한 offer_id와 명시적 동의 전에는 고객 화면에 노출하지 않는다.
    expect(screen.queryByText("정답 보기")).toBeNull();
  });

  it("renders Escape Ops on the game master route", () => {
    render(<MemoryRouter initialEntries={["/game-master"]}><App /></MemoryRouter>);
    expect(screen.getByTitle("ESCAPE OPS 게임마스터 관제 화면").getAttribute("src"))
      .toBe("/escape-ops/index.html");
  });
});
