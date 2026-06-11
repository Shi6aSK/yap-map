#!/usr/bin/env python3
import json
import re
from collections import Counter


TRANSCRIPT = '''
[00:00] Maya: Hey, are you still coming over later or did your lab run late again?

[00:04] Leo: I’m coming, but probably around seven. The lab was supposed to be one hour, and somehow we spent thirty minutes just arguing about why the sensor data looked weird.

[00:13] Maya: Was it actually weird or was someone using the wrong units again?

[00:17] Leo: Wrong units. Classic. Someone logged temperature in Fahrenheit, but the script assumed Celsius. The graph looked like the robot was driving through a volcano.

[00:28] Maya: That’s honestly impressive. You should keep that plot and title it “climate change simulation.”

[00:34] Leo: I might. Anyway, what are you working on?

[00:38] Maya: I’m trying to organize my life, which means I opened Notion, made one beautiful dashboard, and then avoided all my actual tasks.

[00:47] Leo: Productivity cosplay.

[00:49] Maya: Exactly. But I did make a list of things I need to do: apply for internships, email Professor Chen, clean my room, and stop buying coffee every day.

[01:00] Leo: One of those is impossible.

[01:02] Maya: Cleaning my room?

[01:04] Leo: No, the coffee thing. That’s part of your personality now.

[01:08] Maya: Fair. But money is getting scary. I checked my bank account and immediately closed the app like it was a horror movie.

[01:17] Leo: Same. I’ve started doing that thing where I pretend groceries under twenty dollars don’t count.

[01:23] Maya: Financial strategy: denial.

[01:26] Leo: Speaking of groceries, what should we eat tonight? I can cook pasta, but I only have noodles, garlic, and a suspiciously old jar of pesto.

[01:36] Maya: How old?

[01:38] Leo: Emotionally? Ancient. Legally? Maybe two months.

[01:44] Maya: Let’s not risk it. We can make fried rice. I have eggs, frozen vegetables, soy sauce, and leftover rice.

[01:52] Leo: That sounds safer. Also, I’ve been trying to eat better anyway. My smartwatch keeps judging my sleep.

[01:59] Maya: Mine told me I had “poor recovery” after I slept six hours and ate chips for dinner. Like, thank you, tiny wrist therapist.

[02:08] Leo: I want a health tracker that encourages me instead of bullying me.

[02:12] Maya: “Great job breathing today.”

[02:15] Leo: Exactly. Low standards, high morale.

[02:19] Maya: Did you ever decide if you’re going to buy that refurbished laptop?

[02:23] Leo: I’m still thinking. It’s cheap, but the battery is questionable. I want something that can run local AI models, but I also don’t want to accidentally buy a space heater.

[02:34] Maya: What specs?

[02:36] Leo: Sixteen gigs of RAM, older i7, no dedicated GPU. Good enough for coding, not great for machine learning.

[02:44] Maya: Maybe use it as a server? Like for your conversation graph project?

[02:49] Leo: That’s actually what I was thinking. I want to make a tool that listens to a conversation and builds a live graph of topics, people, decisions, and action items.

[03:00] Maya: That sounds useful and slightly terrifying.

[03:03] Leo: Why terrifying?

[03:05] Maya: Because imagine seeing a graph of our conversation. It would start with homework, then jump to pesto safety, then financial anxiety, then robot volcanoes.

[03:16] Leo: That’s the point. Conversations are chaotic, but there’s structure underneath.

[03:21] Maya: Okay, philosopher. How would it know what matters?

[03:25] Leo: It would track repeated topics, named entities, questions, and decisions. Like if we keep mentioning internships, it becomes an important node. If we decide to make fried rice, that becomes a decision node.

[03:39] Maya: So right now, “fried rice” is more important than my future career?

[03:44] Leo: Based on emotional urgency, yes.

[03:48] Maya: Honestly, accurate.

[03:51] Leo: I also want it to work with recorded conversations or videos later. Imagine uploading a two-hour meeting and getting a graph instead of rewatching the whole thing.

[04:01] Maya: That would be amazing for student org meetings. Half the time people forget who agreed to do what.

[04:07] Leo: Exactly. It could extract action items like “Maya will email the venue” or “Leo will update the budget spreadsheet.”

[04:15] Maya: Please do not let an AI hold me accountable. I’m already fighting Google Calendar.

[04:20] Leo: Too late. The graph remembers.

[04:24] Maya: Creepy slogan. Don’t use that.

[04:27] Leo: Fine. “YapMap: because your conversations deserve a conspiracy board.”

[04:33] Maya: That’s actually funny.

[04:35] Leo: I know.

[04:37] Maya: For the graph, would you use bubbles or nodes?

[04:40] Leo: Nodes and edges. Bigger nodes for important topics, thicker edges for stronger relationships. Maybe colors for categories: people, tasks, decisions, questions.

[04:51] Maya: Could it show time? Like how the conversation moved?

[04:55] Leo: Yeah, a timeline slider would be cool. You could scrub through the conversation and watch the graph grow.

[05:02] Maya: That would be so good for podcasts. Like you could see when they moved from politics to movies to personal stories.

[05:09] Leo: Exactly. And for lectures too. Imagine mapping a professor’s lecture into concepts.

[05:15] Maya: That would help me study. Especially when a lecture starts with theory and ends with “this will be on the exam” in the last two minutes.

[05:23] Leo: The graph could mark high-priority segments.

[05:26] Maya: You should build that before finals.

[05:29] Leo: Dangerous assumption that I have time.

[05:32] Maya: You don’t, but that has never stopped you.

[05:35] Leo: True. I started three side projects this semester and finished zero.

[05:40] Maya: That’s not failure. That’s research and development.

[05:44] Leo: I’m putting that on LinkedIn.

[05:47] Maya: Please don’t.

[05:49] Leo: Speaking of LinkedIn, did you see Aaron got an internship in Seattle?

[05:54] Maya: Yeah, at some cloud company, right?

[05:57] Leo: Yeah. He said the interview was mostly system design and behavioral questions.

[06:02] Maya: I need to start preparing. Every time someone says “tell me about yourself,” my brain leaves my body.

[06:09] Leo: Just make a template. Past, present, future. What you study, what you’ve built, what kind of role you want.

[06:17] Maya: That sounds reasonable. My version is usually, “Hi, I am a person with skills, allegedly.”

[06:25] Leo: Strong opener.

[06:27] Maya: Do you think I should apply to startups or bigger companies?

[06:31] Leo: Both. Startups might give you broader work, but bigger companies have better structure. For a summer internship, I’d apply everywhere and decide later.

[06:41] Maya: That’s probably the move. I’m interested in product design, but also data visualization.

[06:47] Leo: Then YapMap needs you.

[06:49] Maya: Are you recruiting me over fried rice?

[06:52] Leo: Yes. Compensation includes dinner and emotional support debugging.

[06:57] Maya: Tempting.

[06:59] Leo: Also, you have good taste. I need the app to look fun, not like enterprise software from 2008.

[07:07] Maya: First design rule: no gray dashboards unless absolutely necessary.

[07:12] Leo: What about dark mode?

[07:14] Maya: Dark mode is fine. But make it feel like a living map, not a database admin panel.

[07:20] Leo: So maybe animated nodes, soft edges, little topic clusters.

[07:25] Maya: Yes. And when a new topic appears, it should pop in gently, not attack the screen.

[07:31] Leo: Noted. No aggressive nodes.

[07:34] Maya: Also, privacy is going to matter a lot. If it listens through a mic, people need to know what is being recorded and where it goes.

[07:43] Leo: Definitely. I want a big recording indicator, local session controls, and maybe an option to delete audio immediately after transcription.

[07:52] Maya: Good. Also maybe “private mode” where it only stores the graph, not the full transcript.

[07:58] Leo: That’s a great idea. Graph-only mode.

[08:01] Maya: And consent mode. Like before a meeting, it shows a QR code or message saying this conversation is being mapped.

[08:09] Leo: That might be overkill for MVP, but important later.

[08:13] Maya: MVP should still not be creepy.

[08:16] Leo: Agreed. MVP: mic permission, visible recording state, delete session button, no hidden recording.

[08:23] Maya: Good. Now I trust the robot slightly more.

[08:27] Leo: Speaking of robots, how’s your drone club thing going?

[08:31] Maya: Pretty good. We’re trying to plan a demo day, but scheduling is impossible. Everyone is free at exactly different times.

[08:40] Leo: Student org law.

[08:42] Maya: We also need to find a better way to explain the project to freshmen. When we say “autonomous navigation,” half of them think it’s too advanced.

[08:51] Leo: Maybe frame it as smaller modules: sensors, controls, mapping, testing, design.

[08:57] Maya: That’s smart. People can join one small piece instead of feeling like they need to understand the whole drone.

[09:04] Leo: YapMap could help there too. Map project meetings into beginner-friendly topics.

[09:09] Maya: You are really trying to make this tool useful for everything.

[09:13] Leo: I have startup founder disease without the startup.

[09:18] Maya: Symptoms include saying “pipeline” too much.

[09:22] Leo: And making diagrams instead of sleeping.

[09:25] Maya: Speaking of sleeping, are you still waking up at 6 a.m.?

[09:29] Leo: I tried for three days. Then I became a night person again. My body rejected productivity.

[09:36] Maya: I think I’m more creative at night, but more anxious too.

[09:41] Leo: Same. Night brain creates ideas and problems.

[09:45] Maya: Morning brain just wants toast.

[09:48] Leo: Honestly, toast is clarity.

[09:51] Maya: We should go on a trip after finals. Somewhere with mountains or a lake.

[09:56] Leo: I’d love that. Maybe Colorado? Or somewhere cheaper, like a state park nearby.

[10:03] Maya: Colorado sounds amazing but expensive. A cabin near a lake might be more realistic.

[10:09] Leo: We could invite Aaron and Priya too.

[10:12] Maya: Yes, but only if we agree not to turn it into a productivity retreat.

[10:17] Leo: No laptops?

[10:19] Maya: One emergency laptop.

[10:22] Leo: That’s how it starts.

[10:24] Maya: Fine. No laptops for the first twenty-four hours.

[10:28] Leo: Deal.

[10:30] Maya: What movie should we watch tonight after dinner?

[10:33] Leo: Something low effort. Maybe a heist movie.

[10:37] Maya: I love heist movies because everyone has one weird skill, and somehow the plan depends on a guy who can skateboard through lasers.

[10:46] Leo: That’s basically group projects.

[10:49] Maya: True. There’s always one person doing lockpicking, one person making slides, and one person missing.

[10:56] Leo: The missing person is the villain.

[10:59] Maya: Plot twist.

[11:01] Leo: We could watch Ocean’s Eleven.

[11:04] Maya: Good choice. Or Knives Out if we want mystery.

[11:08] Leo: Let’s go with Ocean’s Eleven. It fits the “fun but not too emotionally devastating” category.

[11:15] Maya: Decision node: watch Ocean’s Eleven.

[11:18] Leo: Action item: make fried rice.

[11:21] Maya: Risk: old pesto remains unresolved.

[11:25] Leo: We should throw it away.

[11:27] Maya: That is the healthiest decision you’ve made all week.

[11:31] Leo: Growth.

[11:33] Maya: Before you come over, can you bring green onions?

[11:37] Leo: Yes. Anything else?

[11:39] Maya: Maybe sparkling water. And if you see cheap ice cream, get that too.

[11:45] Leo: Define cheap.

[11:47] Maya: Under five dollars, emotionally supportive flavor.

[11:51] Leo: So chocolate.

[11:53] Maya: Obviously.

[11:55] Leo: Okay. I’ll bring green onions, sparkling water, and chocolate ice cream.

[12:01] Maya: Great. Also bring your laptop. I want to see the first version of YapMap.

[12:06] Leo: I thought we banned laptops.

[12:08] Maya: The ban starts during the imaginary lake trip. Tonight I want to judge your UI.

[12:14] Leo: Fair. It’s ugly right now.

[12:17] Maya: Perfect. I love fixing ugly prototypes.

[12:21] Leo: Then you are officially design advisor.

[12:24] Maya: Put that in the graph.

[12:26] Leo: Done. Maya connected to design advisor, fried rice, and anti-gray-dashboard movement.

[12:34] Maya: Finally, a graph that understands me.
'''

SPEAKER_NAMES = {'maya', 'leo'}


def parse_timestamp(ts_raw: str) -> float:
    parts = ts_raw.split(':')
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    return 0.0


def split_segments(text: str):
    segments = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^:]+):\s*(.+)$', line)
        if not match:
            continue
        ts_raw, speaker, content = match.groups()
        segments.append({
            'speaker': speaker.strip(),
            'time': parse_timestamp(ts_raw),
            'text': content.strip(),
        })
    return segments


STOPWORDS = {
    'the', 'and', 'for', 'are', 'you', 'that', 'with', 'this', 'have', 'from', 'was', 'what', 'when', 'where', 'how',
    'a', 'an', 'in', 'on', 'of', 'to', 'is', 'it', 'i', 'we', 'they', 'be', 'as', 'at', 'by', 'or', 'if', 'but', 'not',
    'do', 'so', 'can', 'will', 'just', 'about', 'your', 's', 't', 'm', 'yeah', 'yes', 'no', 'um', 'uh', 'okay', 'ok',
    'like', 'right', 'well', 'actually', 'basically', 'you', 'know', 'kind', 'got', 'get', 'gonna', 'going', 'today', 'now',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'still', 'really', 'pretty', 'maybe',
    'also', 'would', 'could', 'should', 'need', 'want', 'make', 'made', 'thing', 'things', 'person', 'people', 'good',
    'great', 'same', 'time', 'later', 'tonight', 'every', 'each', 'there', 'here', 'them', 'him', 'her', 'their', 'our',
    'because', 'before', 'after', 'into', 'over', 'under', 'again', 'more', 'most', 'much', 'many', 'some', 'any', 'all',
    'too', 'then', 'node', 'topic', 'fried', 'say', 'said', 'using', 'use', 'used', 'new', 'old', 'very', 'kind',
}


def normalize_token(word: str) -> str:
    token = re.sub(r'[^a-z0-9]', '', word.lower())
    if not token:
        return ''
    if len(token) > 5 and token.endswith('ies'):
        token = token[:-3] + 'y'
    elif len(token) > 2 and token.endswith('s'):
        token = token[:-1]
    return token


def tokenize(text: str):
    tokens = []
    for raw in re.split(r'\s+', text.lower()):
        token = normalize_token(raw)
        if not token or len(token) < 3:
            continue
        if any(ch.isdigit() for ch in token):
            continue
        if token in STOPWORDS or token in SPEAKER_NAMES:
            continue
        tokens.append(token)
    return tokens


def build_graph_patch(segments):
    full_text = ' '.join(segment['text'] for segment in segments)
    tokens = tokenize(full_text)

    unigram_counts = Counter(tokens)
    bigram_counts = Counter()
    for index in range(len(tokens) - 1):
        bigram_counts[f'{tokens[index]} {tokens[index + 1]}'] += 1

    scores = {}
    for phrase, count in bigram_counts.items():
        scores[phrase] = scores.get(phrase, 0) + count * 4
    for phrase, count in unigram_counts.items():
        scores[phrase] = max(scores.get(phrase, 0), int(count * 1.5))

    ranked = sorted(scores.items(), key=lambda item: (-item[1], -len(item[0])))
    topics = []
    for phrase, _score in ranked:
        if len(topics) >= 20:
            break
        if any(ch.isdigit() for ch in phrase):
            continue
        if len(phrase.split()) > 4:
            continue
        topics.append(phrase)

    if not topics:
        topics = [word for word, _count in unigram_counts.most_common(12)]

    nodes = []
    topic_ids = {}
    for topic in topics:
        node_id = 'topic:' + re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')
        topic_ids[topic] = node_id
        nodes.append({'id': node_id, 'label': topic, 'timestamps': []})

    edge_counts = Counter()
    for segment in segments:
        seg_tokens = set(tokenize(segment['text']))
        present = []
        for topic in topics:
            topic_tokens = [part for part in re.split(r'\s+', topic) if part]
            if all(normalize_token(part) in seg_tokens for part in topic_tokens):
                present.append(topic_ids[topic])
                for node in nodes:
                    if node['id'] == topic_ids[topic]:
                        node['timestamps'].append(segment['time'])
                        break
        for index in range(len(present)):
            for j in range(index + 1, len(present)):
                key = '__'.join(sorted([present[index], present[j]]))
                edge_counts[key] += 1

    edges = []
    for key, value in edge_counts.items():
        source, target = key.split('__')
        edges.append({'id': key, 'source': source, 'target': target, 'value': value})

    return {'nodesAdded': nodes, 'edgesAdded': edges}


def main():
    segments = split_segments(TRANSCRIPT)
    payload = build_graph_patch(segments)
    output = {
        'graph_patch': payload,
        'analysis': {
            'num_segments': len(segments),
            'sample_segments': [(segment['speaker'], segment['time'], segment['text']) for segment in segments[:6]],
        },
    }
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()