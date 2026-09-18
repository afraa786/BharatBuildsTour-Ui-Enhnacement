"use client";

import { useState } from "react";

type Stage = "Quote ready" | "Accepted" | "Payment pending" | "Paid" | "Invoiced";

const formatMoney = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paise / 100);

const stages: Stage[] = ["Quote ready", "Accepted", "Payment pending", "Paid", "Invoiced"];

const products = [
  ["MCB-32A-SP", "32A SP MCB C Curve", "38 each", "Healthy"],
  ["WIRE-1.5SQ-RED", "1.5 sq mm FR Copper Wire Red", "450 m", "Healthy"],
  ["LED-9W", "9W LED Bulb Cool Day Light", "20 each", "Low stock"],
];

export default function Home() {
  const [stage, setStage] = useState<Stage>("Quote ready");
  const [notice, setNotice] = useState("Quote QT-8F31A2 is ready for review.");
  const [command, setCommand] = useState("");
  const [commandResult, setCommandResult] = useState("Try “show low stock” or “show vendor updates”.");
  const stageIndex = stages.indexOf(stage);

  function advance() {
    const next = stages[stageIndex + 1];
    if (!next) return;
    setStage(next);
    setNotice(
      next === "Accepted"
        ? "Buyer accepted quote version 1. Create a secure payment link."
        : next === "Payment pending"
          ? "Payment link PAY-24BC91 created. Awaiting secure provider confirmation."
          : next === "Paid"
            ? "Payment confirmed. The invoice can now be generated."
            : "Invoice SA/2026/0001 generated once; retries return the same record.",
    );
  }

  function runCommand(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = command.trim().toLowerCase();
    if (normalized === "show low stock") {
      setCommandResult("LED-9W has 20 each available; reorder threshold is 30. One active RFQ may be affected.");
    } else if (normalized === "show vendor updates") {
      setCommandResult("Lumina Electricals revised LED prices effective 20 September. Review open LED quotes.");
    } else if (normalized === "show pending payments") {
      setCommandResult(stage === "Payment pending" ? "PAY-24BC91 is pending for Acme Electrical Contractors." : "No pending payments in this demo run.");
    } else {
      setCommandResult("Command not recognized. Try “show low stock”, “show vendor updates”, or “show pending payments”.");
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">S</span><span>StockAware</span></div>
        <p className="workspace">Aarav Electricals<br /><strong>Manager control room</strong></p>
        <nav aria-label="Primary navigation">
          <a className="active" href="#overview">Overview</a>
          <a href="#runs">Active runs <span>1</span></a>
          <a href="#approvals">Approvals</a>
          <a href="#inventory">Inventory</a>
          <a href="#updates">Manager updates</a>
        </nav>
        <div className="side-footer"><span className="status-dot" /> Demo environment<br /><small>Payment confirmation is simulated.</small></div>
      </aside>

      <section className="content" id="overview">
        <header>
          <div><p className="eyebrow">THURSDAY, 18 SEPTEMBER</p><h1>Good morning, Aamir.</h1><p className="subtle">Here’s what needs your attention today.</p></div>
          <button className="outline">Daily summary ↗</button>
        </header>

        <section className="metrics" aria-label="Today’s metrics">
          <article><span>Active quote value</span><strong>{formatMoney(725000)}</strong><small>1 quote in progress</small></article>
          <article><span>Needs attention</span><strong className="orange">2</strong><small>Low stock and vendor update</small></article>
          <article><span>Payments pending</span><strong>{stage === "Payment pending" ? "1" : "0"}</strong><small>{stage === "Payment pending" ? "₹7,250 awaiting payment" : "No open payment links"}</small></article>
          <article><span>Today’s conversion</span><strong>68%</strong><small>Up 12% from yesterday</small></article>
        </section>

        <div className="grid">
          <section className="card run-card" id="runs">
            <div className="section-title"><div><p className="eyebrow">LIVE RUN</p><h2>Acme Electrical Contractors</h2></div><span className="pill">{stage}</span></div>
            <p className="run-copy">20 × 32A SP MCB C Curve · 100 m × 1.5 sq mm FR Copper Wire Red</p>
            <div className="amount-row"><div><span>Quote QT-8F31A2 · Version 1</span><strong>{formatMoney(725000)}</strong></div><button onClick={advance} disabled={stage === "Invoiced"}>{stage === "Quote ready" ? "Accept quote" : stage === "Accepted" ? "Create payment link" : stage === "Payment pending" ? "Confirm demo payment" : stage === "Paid" ? "Generate invoice" : "Invoice issued"}</button></div>
            <p className="notice"><span className="status-dot" /> {notice}</p>
            <ol className="progress" aria-label="Quote progress">{stages.map((item, index) => <li className={index <= stageIndex ? "complete" : ""} key={item}><i>{index < stageIndex ? "✓" : index + 1}</i><span>{item}</span></li>)}</ol>
          </section>

          <section className="card manager" id="updates">
            <div className="section-title"><div><p className="eyebrow">MANAGER UPDATE</p><h2>Two items need a decision</h2></div><span className="spark">✦</span></div>
            <div className="update high"><b>Vendor price revision</b><p>Lumina Electricals revised LED prices, effective 20 September.</p><button>Review affected quotes →</button></div>
            <div className="update"><b>Low stock · LED-9W</b><p>20 each available; reorder threshold is 30.</p><button>View inventory →</button></div>
          </section>
        </div>

        <div className="grid lower">
          <section className="card inventory" id="inventory"><div className="section-title"><div><p className="eyebrow">CATALOG SNAPSHOT</p><h2>Inventory signals</h2></div><a href="#inventory">View all →</a></div><table><thead><tr><th>SKU</th><th>Product</th><th>Available</th><th>State</th></tr></thead><tbody>{products.map(([sku, name, available, state]) => <tr key={sku}><td>{sku}</td><td>{name}</td><td>{available}</td><td><span className={state === "Low stock" ? "state low" : "state"}>{state}</span></td></tr>)}</tbody></table></section>
          <section className="card command"><p className="eyebrow">ASK THE MANAGER</p><h2>Operational command desk</h2><p className="subtle">Get concise answers from saved business events.</p><form onSubmit={runCommand}><label htmlFor="command">Admin command</label><div><input id="command" value={command} onChange={(event) => setCommand(event.target.value)} placeholder="show low stock" /><button type="submit">Run</button></div></form><output>{commandResult}</output></section>
        </div>
      </section>
    </main>
  );
}
