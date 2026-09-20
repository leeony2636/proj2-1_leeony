import type { ReactNode } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

function Shell({ role, children }: { role: string; children: ReactNode }) {
  return <main className="shell"><nav><Link to="/customer">고객 화면</Link><Link to="/game-master">게임마스터 화면</Link></nav><section className="card"><p className="eyebrow">ESCAPE ROOM AGENT</p><h1>{role}</h1>{children}</section></main>;
}

function Customer() { return <Shell role="힌트가 필요할 때 질문하세요"><p>현재 세션의 퍼즐 상황에 맞춰 단계적인 힌트를 제공합니다.</p><textarea aria-label="hint request" placeholder="예: 이 퍼즐의 다음 단계를 알려주세요" /><button>힌트 요청</button></Shell>; }
function GameMaster() { return <Shell role="게임 진행 상태"><p>세션을 만들고 고객 요청 및 장비 이상 신고를 확인합니다.</p><button>세션 시작</button><button className="secondary">요청 큐 확인</button></Shell>; }
export default function App() { return <Routes><Route path="/" element={<Navigate to="/customer" replace />} /><Route path="/customer" element={<Customer />} /><Route path="/game-master" element={<GameMaster />} /></Routes>; }
