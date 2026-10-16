> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Multi-agent

Multi-agent systems coordinate specialized components to tackle complex workflows. However, not every complex task requires this approach—a single agent with the right (sometimes dynamic) tools and prompt can often achieve similar results.

<Tip>
  For built-in multi-agent support, use [Deep Agents](/oss/python/deepagents/overview): a higher-level harness built on LangChain that ships with [subagents](/oss/python/deepagents/subagents), [skills](/oss/python/deepagents/skills), planning, a virtual filesystem, and context management.
</Tip>

## Why multi-agent?

When developers say they need "multi-agent," they're usually looking for one or more of these capabilities:

* <Icon icon="brain" /> **Context management**: Provide specialized knowledge without overwhelming the model's context window. If context were infinite and latency zero, you could dump all knowledge into a single prompt—but since it's not, you need patterns to selectively surface relevant information.
* <Icon icon="users" /> **Distributed development**: Allow different teams to develop and maintain capabilities independently, composing them into a larger system with clear boundaries.
* <Icon icon="git-branch" /> **Parallelization**: Spawn specialized workers for subtasks and execute them concurrently for faster results.

Multi-agent patterns are particularly valuable when a single agent has too many [tools](/oss/python/langchain/tools) and makes poor decisions about which to use, when tasks require specialized knowledge with extensive context (long prompts and domain-specific tools), or when you need to enforce sequential constraints that unlock capabilities only after certain conditions are met.

<Tip>
  At the center of multi-agent design is **[context engineering](/oss/python/langchain/context-engineering)**—deciding what information each agent sees. The quality of your system depends on ensuring each agent has access to the right data for its task.
</Tip>

## Patterns

Here are the main patterns for building multi-agent systems, each suited to different use cases:

| Pattern | How it works |
| - | - |
| [**Subagents**](/oss/python/langchain/multi-agent/subagents) | A main agent coordinates subagents as tools. All routing passes through the main agent, which decides when and how to invoke each subagent. |
| [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | Behavior changes dynamically based on state. Tool calls update a state variable that triggers routing or configuration changes, switching agents or adjusting the current agent's tools and prompt. |
| [**Skills**](/oss/python/langchain/multi-agent/skills) | Specialized prompts and knowledge loaded on-demand. A single agent stays in control while loading context from skills as needed. |
| [**Router**](/oss/python/langchain/multi-agent/router) | A routing step classifies input and directs it to one or more specialized agents. Results are synthesized into a combined response. |
| [**Custom workflow**](/oss/python/langchain/multi-agent/custom-workflow) | Build bespoke execution flows with [LangGraph](/oss/python/langgraph/overview), mixing deterministic logic and agentic behavior. Embed other patterns as nodes in your workflow. |

### Choosing a pattern

Use this table to match your requirements to the right pattern:

<div className="compact-first-col">
  | Pattern | Distributed development | Parallelization | Multi-hop | Direct user interaction |
  | - | :-: | :-: | :-: | :-: |
  | [**Subagents**](/oss/python/langchain/multi-agent/subagents) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
  | [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | - | - | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
  | [**Skills**](/oss/python/langchain/multi-agent/skills) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
  | [**Router**](/oss/python/langchain/multi-agent/router) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | - | ⭐⭐⭐ |
</div>

* **Distributed development**: Can different teams maintain components independently?
* **Parallelization**: Can multiple agents execute concurrently?
* **Multi-hop**: Does the pattern support calling multiple subagents in series?
* **Direct user interaction**: Can subagents converse directly with the user?

<Tip>
  You can mix patterns! For example, a **subagents** architecture can invoke tools that invoke custom workflows or router agents. Subagents can even use the **skills** pattern to load context on-demand. The possibilities are endless!
</Tip>

### Visual overview

<Tabs>
  <Tab title="Subagents">
    A main agent coordinates subagents as tools. All routing passes through the main agent.

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/pattern-subagents.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=f924dde09057820b08f0c577e08fcfe7" alt="Subagents pattern: main agent coordinates subagents as tools" width="1020" height="734" data-path="oss/langchain/multi-agent/images/pattern-subagents.png" />
    </Frame>
  </Tab>

  <Tab title="Handoffs">
    Agents transfer control to each other via tool calls. Each agent can hand off to others or respond directly to the user.

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/pattern-handoffs.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=57d935e6a8efab4afb3faa385113f4dd" alt="Handoffs pattern: agents transfer control via tool calls" width="1568" height="464" data-path="oss/langchain/multi-agent/images/pattern-handoffs.png" />
    </Frame>
  </Tab>

  <Tab title="Skills">
    A single agent loads specialized prompts and knowledge on-demand while staying in control.

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/pattern-skills.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=119131d1f19be1f0c6fb1e30f080b427" alt="Skills pattern: single agent loads specialized context on-demand" width="874" height="734" data-path="oss/langchain/multi-agent/images/pattern-skills.png" />
    </Frame>
  </Tab>

  <Tab title="Router">
    A routing step classifies input and directs it to specialized agents. Results are synthesized.

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/pattern-router.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=ceab32819240ba87f3a132357cc78b09" alt="Router pattern: routing step classifies input to specialized agents" width="1560" height="556" data-path="oss/langchain/multi-agent/images/pattern-router.png" />
    </Frame>
  </Tab>
</Tabs>

<Tip>
  Trace the full coordination flow across agents with [LangSmith](https://smith.langchain.com?utm_source=docs\&utm_medium=cta\&utm_campaign=langsmith-signup\&utm_content=oss-langchain-multi-agent-index). Follow the [tracing quickstart](/langsmith/trace-with-langchain) to get set up.

  We recommend you also set up [LangSmith Engine](/langsmith/engine) which monitors your traces, detects issues, and proposes fixes.
</Tip>

## Performance comparison

Different patterns have different performance characteristics. Understanding these tradeoffs helps you choose the right pattern for your latency and cost requirements.

**Key metrics:**

* **Model calls**: Number of LLM invocations. More calls = higher latency (especially if sequential) and higher per-request API costs.
* **Tokens processed**: Total [context window](/oss/python/langchain/context-engineering) usage across all calls. More tokens = higher processing costs and potential context limits.

### One-shot request

> **User:** "Buy coffee"

A specialized coffee agent/skill can call a `buy_coffee` tool.

| Pattern | Model calls | Best fit |
| - | :-: | :-: |
| [**Subagents**](/oss/python/langchain/multi-agent/subagents) | 4 | |
| [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | 3 | ✅ |
| [**Skills**](/oss/python/langchain/multi-agent/skills) | 3 | ✅ |
| [**Router**](/oss/python/langchain/multi-agent/router) | 3 | ✅ |

<Tabs>
  <Tab title="Subagents">
    **4 model calls:**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/oneshot-subagents.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=bd4eeef41d8870bfa887dd0aa97d0b79" alt="Subagents one-shot: 4 model calls for buy coffee request" width="1568" height="1124" data-path="oss/langchain/multi-agent/images/oneshot-subagents.png" />
    </Frame>
  </Tab>

  <Tab title="Handoffs">
    **3 model calls:**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/oneshot-handoffs.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=42ec50519ff04f034050dc77cf869907" alt="Handoffs one-shot: 3 model calls for buy coffee request" width="1568" height="948" data-path="oss/langchain/multi-agent/images/oneshot-handoffs.png" />
    </Frame>
  </Tab>

  <Tab title="Skills">
    **3 model calls:**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/oneshot-skills.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=c8dbf69ed4509e30e5280e7e8a391dab" alt="Skills one-shot: 3 model calls for buy coffee request" width="1568" height="1036" data-path="oss/langchain/multi-agent/images/oneshot-skills.png" />
    </Frame>
  </Tab>

  <Tab title="Router">
    **3 model calls:**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/oneshot-router.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=be5707931d3e520e3ae66af544f2cf2f" alt="Router one-shot: 3 model calls for buy coffee request" width="1568" height="994" data-path="oss/langchain/multi-agent/images/oneshot-router.png" />
    </Frame>
  </Tab>
</Tabs>

**Key insight:** Handoffs, Skills, and Router are most efficient for single tasks (3 calls each). Subagents adds one extra call because results flow back through the main agent—this overhead provides centralized control.

### Repeat request

> **Turn 1:** "Buy coffee"
> **Turn 2:** "Buy coffee again"

The user repeats the same request in the same conversation.

<div className="compact-first-col">
  | Pattern | Turn 2 calls | Total (both turns) | Best fit |
  | - | :-: | :-: | :-: |
  | [**Subagents**](/oss/python/langchain/multi-agent/subagents) | 4 | 8 | |
  | [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | 2 | 5 | ✅ |
  | [**Skills**](/oss/python/langchain/multi-agent/skills) | 2 | 5 | ✅ |
  | [**Router**](/oss/python/langchain/multi-agent/router) | 3 | 6 | |
</div>

<Tabs>
  <Tab title="Subagents">
    **4 calls again → 8 total**

    * Subagents are **stateless by design**—each invocation follows the same flow
    * The main agent maintains conversation context, but subagents start fresh each time
    * This provides strong context isolation but repeats the full flow
  </Tab>

  <Tab title="Handoffs">
    **2 calls → 5 total**

    * The coffee agent is **still active** from turn 1 (state persists)
    * No handoff needed—agent directly calls `buy_coffee` tool (call 1)
    * Agent responds to user (call 2)
    * **Saves 1 call by skipping the handoff**
  </Tab>

  <Tab title="Skills">
    **2 calls → 5 total**

    * The skill context is **already loaded** in conversation history
    * No need to reload—agent directly calls `buy_coffee` tool (call 1)
    * Agent responds to user (call 2)
    * **Saves 1 call by reusing loaded skill**
  </Tab>

  <Tab title="Router">
    **3 calls again → 6 total**

    * Routers are **stateless**—each request requires an LLM routing call
    * Turn 2: Router LLM call (1) → Milk agent calls buy\_coffee (2) → Milk agent responds (3)
    * Can be optimized by wrapping as a tool in a stateful agent
  </Tab>
</Tabs>

**Key insight:** Stateful patterns (Handoffs, Skills) save 40-50% of calls on repeat requests. Subagents maintain consistent cost per request—this stateless design provides strong context isolation but at the cost of repeated model calls.

### Multi-domain

> **User:** "Compare Python, JavaScript, and Rust for web development"

Each language agent/skill contains \~2000 tokens of documentation. All patterns can make parallel tool calls.

| Pattern | Model calls | Total tokens | Best fit |
| - | :-: | :-: | :-: |
| [**Subagents**](/oss/python/langchain/multi-agent/subagents) | 5 | \~9K | ✅ |
| [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | 7+ | \~14K+ | |
| [**Skills**](/oss/python/langchain/multi-agent/skills) | 3 | \~15K | |
| [**Router**](/oss/python/langchain/multi-agent/router) | 5 | \~9K | ✅ |

<Tabs>
  <Tab title="Subagents">
    **5 calls, \~9K tokens**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/multidomain-subagents.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=9cc5d2d46bfa98b7ceeacdc473512c94" alt="Subagents multi-domain: 5 calls with parallel execution" width="1568" height="1232" data-path="oss/langchain/multi-agent/images/multidomain-subagents.png" />
    </Frame>

    Each subagent works in **isolation** with only its relevant context. Total: **9K tokens**.
  </Tab>

  <Tab title="Handoffs">
    **7+ calls, \~14K+ tokens**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/multidomain-handoffs.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=7ede44260515e49ff1d0217f0030d66d" alt="Handoffs multi-domain: 7+ sequential calls" width="1568" height="834" data-path="oss/langchain/multi-agent/images/multidomain-handoffs.png" />
    </Frame>

    Handoffs executes **sequentially**—can't research all three languages in parallel. Growing conversation history adds overhead. Total: **\~14K+ tokens**.
  </Tab>

  <Tab title="Skills">
    **3 calls, \~15K tokens**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/multidomain-skills.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=2162584b6076aee83396760bc6de4cf4" alt="Skills multi-domain: 3 calls with accumulated context" width="1560" height="988" data-path="oss/langchain/multi-agent/images/multidomain-skills.png" />
    </Frame>

    After loading, **every subsequent call processes all 6K tokens of skill documentation**. Subagents processes 67% fewer tokens overall due to context isolation. Total: **15K tokens**.
  </Tab>

  <Tab title="Router">
    **5 calls, \~9K tokens**

    <Frame>
      <img src="https://mintcdn.com/langchain-5e9cc07a/CRpSg52QqwDx49Bw/oss/langchain/multi-agent/images/multidomain-router.png?fit=max&auto=format&n=CRpSg52QqwDx49Bw&q=85&s=ef11573bc65e5a2996d671bb3030ca6b" alt="Router multi-domain: 5 calls with parallel execution" width="1568" height="1052" data-path="oss/langchain/multi-agent/images/multidomain-router.png" />
    </Frame>

    Router uses an **LLM for routing**, then invokes agents in parallel. Similar to Subagents but with explicit routing step. Total: **9K tokens**.
  </Tab>
</Tabs>

**Key insight:** For multi-domain tasks, patterns with parallel execution (Subagents, Router) are most efficient. Skills has fewer calls but high token usage due to context accumulation. Handoffs is inefficient here—it must execute sequentially and can't leverage parallel tool calling for consulting multiple domains simultaneously.

### Summary

Here's how patterns compare across all three scenarios:

<div className="compact-first-col">
  | Pattern | One-shot | Repeat request | Multi-domain |
  | - | :-: | :-: | :-: |
  | [**Subagents**](/oss/python/langchain/multi-agent/subagents) | 4 calls | 8 calls (4+4) | 5 calls, 9K tokens |
  | [**Handoffs**](/oss/python/langchain/multi-agent/handoffs) | 3 calls | 5 calls (3+2) | 7+ calls, 14K+ tokens |
  | [**Skills**](/oss/python/langchain/multi-agent/skills) | 3 calls | 5 calls (3+2) | 3 calls, 15K tokens |
  | [**Router**](/oss/python/langchain/multi-agent/router) | 3 calls | 6 calls (3+3) | 5 calls, 9K tokens |
</div>

**Choosing a pattern:**

<div className="compact-first-col">
  | Optimize for | [Subagents](/oss/python/langchain/multi-agent/subagents) | [Handoffs](/oss/python/langchain/multi-agent/handoffs) | [Skills](/oss/python/langchain/multi-agent/skills) | [Router](/oss/python/langchain/multi-agent/router) |
  | - | :-: | :-: | :-: | :-: |
  | Single requests | | ✅ | ✅ | ✅ |
  | Repeat requests | | ✅ | ✅ | |
  | Parallel execution | ✅ | | | ✅ |
  | Large-context domains | ✅ | | | ✅ |
  | Simple, focused tasks | | | ✅ | |
</div>

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langchain/multi-agent/index.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
