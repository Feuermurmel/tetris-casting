import math
import pyscad


tau = 2 * math.pi


def polygon(pts):
	return pyscad.Object.create(pyscad.Selection.create(pyscad.Node.create('linear_extrude(1, false) {{ {}; }}'.format(pyscad._str_call('polygon', points = pts, paths = [list(range(len(pts)))])))))


class Node:
	def __init__(self, inside_pts, outside_pts, direction_diff):
		self.inside_pts = inside_pts
		self.outside_pts = outside_pts
		self.direction_diff = direction_diff


nodes = {
	's': Node([(0, -1), (1, 0), (0, 1)], [], 0), # straight
	'r': Node([(0, 0)], [(-1, 1)], 1), # left
	'l': Node([(0, 0)], [(-1, -1)], -1) } # right


def pattern_size(pattern):
	size_x = len(pattern[0])
	size_y = len(pattern)
	
	assert all(len(i) == size_x for i in pattern)
	
	return size_x, size_y


def get_tile(pattern, x, y):
	size_x, size_y = pattern_size(pattern)
	
	return 0 <= x < size_x and 0 <= y < size_y and bool(int(pattern[y][x]))


def rotate(pt, direction):
	x, y = pt
	
	for i in range(direction):
		x, y = -y, x
	
	return x, y


def rotate_pattern(pattern, direction):
	for i in range(direction):
		size_x, size_y = pattern_size(pattern)
		pattern = [[get_tile(pattern, iy, size_y - ix - 1) for ix in range(size_y)] for iy in range(size_x)]
	
	return pattern


def create_part(pattern):
	wall_thickness = 1
	wall_height = 9
	tile_size = 8
	groove_depth = 1
	groove_width = 1
	
	piece_height = wall_height + wall_thickness
	
	eps = 1e-3
	floor = pyscad.cube.scale(x = tile_size, y = tile_size).scale(
		z = wall_thickness).move(z = -wall_thickness)
	wall = pyscad.cube.scale(x = wall_thickness, y = tile_size + 2 * eps,
		z = piece_height).move(x = tile_size, y = -eps, z = -wall_thickness)
	tile_prism = polygon([(0, 0), (1 + eps, -eps), (-eps, 1 + eps)]).scale(z = tile_size)
	height_prism = polygon([(-eps, -1 - eps), (1, 0), (-eps, 1 + eps)]).scale(z = piece_height)

	objects = [
		(['1'], floor),
		(['10'], wall),
		(['11'], tile_prism.rotate(x = tau / 4).move(x = tile_size, y = tile_size)),
		(['10', '00'], height_prism.rotate(z = 0).move(x = tile_size, y = tile_size, z = -wall_thickness)),
		(['11', '00'], height_prism.rotate(z = -tau / 4).move(x = tile_size, y = tile_size, z = -wall_thickness))]
	
	size_x, size_y = pattern_size(pattern)
	
	def fn():
		for mask, object in objects:
			for d in range(0, 4):
				m_rotated = rotate_pattern(mask, d)
				m_size_x, m_size_y = pattern_size(m_rotated)
				
				corner_x, corner_y = rotate(pattern_size(mask), d)
				offset_x = min(0, corner_x)
				offset_y = min(0, corner_y)
				
				for iy in range(-1, size_y - m_size_y + 2):
					for ix in range(-1, size_x - m_size_x + 2):
						if all(get_tile(pattern, ix + ixm, iy + iym) == get_tile(m_rotated, ixm, iym) for ixm in range(m_size_x) for iym in range(m_size_y)):
							move_x = ix - offset_x
							move_y = iy - offset_y
							
							yield object.rotate(z = tau / 4 * d).move(x = move_x * tile_size, y = move_y * tile_size)
	
	return pyscad.union(fn())


patterns = dict(
	T = ['111', '010'],
	L = ['111', '001'],
	O = ['11', '11'],
	I = ['1111'],
	S = ['110', '011'] )


for name, pattern in patterns.items():
	pyscad.write_scad(create_part(pattern), path = 'parts/{}.scad'.format(name))
