'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Slider,
  Group,
  Text,
  Chip,
  Paper,
  Stack,
  Loader,
  Center,
} from '@mantine/core';
import { useApi } from '@/hooks/useApi';

interface GraphNode {
  id: string;
  name: string;
  score: number;
  platform: string;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const PLATFORM_COLORS: Record<string, string> = {
  gmail: '#e03131',
  facebook: '#1c7ed6',
  instagram: '#ae3ec9',
  reddit: '#e8590c',
  you: '#37b24d',
};

const DEFAULT_COLOR = '#868e96';

const ALL_PLATFORMS = ['gmail', 'facebook', 'instagram', 'reddit'];

// D3 simulation mutates nodes by adding x, y, vx, vy, fx, fy.
// We define a sim-node type that carries our domain fields alongside D3 fields.
interface SimNode {
  id: string;
  name: string;
  score: number;
  platform: string;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
  weight: number;
}

export function RelationshipGraph() {
  const router = useRouter();
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [minScore, setMinScore] = useState(0);
  const [activePlatforms, setActivePlatforms] = useState<string[]>(ALL_PLATFORMS);

  const { data, isLoading } = useApi<GraphData>('/api/people/graph');

  const navigateToPerson = useCallback(
    (id: string) => {
      if (id !== 'you') {
        router.push(`/people/${id}`);
      }
    },
    [router]
  );

  useEffect(() => {
    if (!data || !svgRef.current) return;

    // Dynamically import d3 to avoid SSR issues
    let cancelled = false;

    (async () => {
      const d3 = await import('d3');
      if (cancelled || !svgRef.current) return;

      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const width = svgRef.current.clientWidth || 800;
      const height = svgRef.current.clientHeight || 600;

      // Filter nodes by score and platform
      const filteredNodes = data.nodes.filter((n) => {
        if (n.id === 'you') return true;
        if (n.score < minScore) return false;
        if (activePlatforms.length > 0 && n.platform && !activePlatforms.includes(n.platform.toLowerCase())) {
          return false;
        }
        return true;
      });

      const nodeIds = new Set(filteredNodes.map((n) => n.id));
      const filteredEdges = data.edges.filter(
        (e) => nodeIds.has(e.source) && nodeIds.has(e.target)
      );

      // Deep clone to avoid D3 mutating original data
      const nodes: SimNode[] = filteredNodes.map((n) => ({ ...n }));
      const edges: SimLink[] = filteredEdges.map((e) => ({ ...e }));

      // Set up zoom
      const g = svg.append('g');

      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 5])
        .on('zoom', (event) => {
          g.attr('transform', event.transform);
        });

      svg.call(zoom);

      // Build simulation
      const simulation = d3
        .forceSimulation<SimNode>(nodes)
        .force(
          'link',
          d3
            .forceLink<SimNode, SimLink>(edges)
            .id((d) => d.id)
            .distance(100)
        )
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

      // Edges
      const link = g
        .append('g')
        .selectAll<SVGLineElement, SimLink>('line')
        .data(edges)
        .enter()
        .append('line')
        .attr('stroke', '#495057')
        .attr('stroke-opacity', 0.5)
        .attr('stroke-width', (d) => Math.max(1, d.weight * 3));

      // Node groups
      const node = g
        .append('g')
        .selectAll<SVGGElement, SimNode>('g')
        .data(nodes)
        .enter()
        .append('g')
        .attr('cursor', 'pointer')
        .on('click', (_event, d) => {
          navigateToPerson(d.id);
        })
        .on('mouseenter', (_event, d) => {
          if (tooltipRef.current) {
            tooltipRef.current.style.display = 'block';
            tooltipRef.current.textContent = `${d.name} (${Math.round(d.score * 100)}%)`;
          }
        })
        .on('mousemove', (event) => {
          if (tooltipRef.current) {
            const [x, y] = d3.pointer(event, svgRef.current);
            tooltipRef.current.style.left = `${x + 15}px`;
            tooltipRef.current.style.top = `${y - 10}px`;
          }
        })
        .on('mouseleave', () => {
          if (tooltipRef.current) {
            tooltipRef.current.style.display = 'none';
          }
        })
        .call(
          d3
            .drag<SVGGElement, SimNode>()
            .on('start', (event, d) => {
              if (!event.active) simulation.alphaTarget(0.3).restart();
              d.fx = d.x;
              d.fy = d.y;
            })
            .on('drag', (event, d) => {
              d.fx = event.x;
              d.fy = event.y;
            })
            .on('end', (event, d) => {
              if (!event.active) simulation.alphaTarget(0);
              d.fx = null;
              d.fy = null;
            })
        );

      // Circles
      node
        .append('circle')
        .attr('r', (d) => (d.id === 'you' ? 20 : 8 + d.score * 12))
        .attr('fill', (d) => {
          if (d.id === 'you') return PLATFORM_COLORS.you;
          return PLATFORM_COLORS[d.platform?.toLowerCase()] ?? DEFAULT_COLOR;
        })
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5);

      // Labels
      node
        .append('text')
        .text((d) => d.name)
        .attr('text-anchor', 'middle')
        .attr('dy', (d) => (d.id === 'you' ? 30 : 8 + d.score * 12 + 14))
        .attr('fill', '#c1c2c5')
        .attr('font-size', (d) => (d.id === 'you' ? '13px' : '11px'))
        .attr('pointer-events', 'none');

      // Tick
      simulation.on('tick', () => {
        link
          .attr('x1', (d) => (d.source as SimNode).x ?? 0)
          .attr('y1', (d) => (d.source as SimNode).y ?? 0)
          .attr('x2', (d) => (d.target as SimNode).x ?? 0)
          .attr('y2', (d) => (d.target as SimNode).y ?? 0);

        node.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
      });

      // Cleanup
      return () => {
        simulation.stop();
      };
    })();

    return () => {
      cancelled = true;
    };
  }, [data, minScore, activePlatforms, navigateToPerson]);

  if (isLoading) {
    return (
      <Center py="xl">
        <Loader />
      </Center>
    );
  }

  return (
    <Stack gap="md">
      {/* Filter controls */}
      <Paper p="sm" radius="md" withBorder>
        <Group gap="xl" align="flex-end">
          <Box style={{ flex: 1, minWidth: 200 }}>
            <Text size="sm" fw={500} mb={4}>
              Minimum Interaction Score
            </Text>
            <Slider
              value={minScore}
              onChange={setMinScore}
              min={0}
              max={1}
              step={0.05}
              marks={[
                { value: 0, label: '0' },
                { value: 0.5, label: '0.5' },
                { value: 1, label: '1' },
              ]}
              label={(v) => `${Math.round(v * 100)}%`}
            />
          </Box>
          <Box>
            <Text size="sm" fw={500} mb={4}>
              Platforms
            </Text>
            <Chip.Group multiple value={activePlatforms} onChange={setActivePlatforms}>
              <Group gap={4}>
                {ALL_PLATFORMS.map((p) => (
                  <Chip key={p} value={p} size="xs" variant="light">
                    {p}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Box>
        </Group>
      </Paper>

      {/* Graph */}
      <Box pos="relative" style={{ width: '100%', height: 600, overflow: 'hidden' }}>
        <svg
          ref={svgRef}
          style={{ width: '100%', height: '100%', background: 'var(--mantine-color-dark-7)', borderRadius: 8 }}
        />
        <div
          ref={tooltipRef}
          style={{
            display: 'none',
            position: 'absolute',
            background: 'var(--mantine-color-dark-5)',
            color: '#c1c2c5',
            padding: '4px 8px',
            borderRadius: 4,
            fontSize: 12,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
          }}
        />
      </Box>
    </Stack>
  );
}
