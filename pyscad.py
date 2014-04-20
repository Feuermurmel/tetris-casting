import abc, numbers, contextlib, os, functools, operator, itertools, math, shutil


def _str_expr(e):
	if isinstance(e, (tuple, list)):
		return '[{}]'.format(', '.join(map(_str_expr, e)))
	else:
		return str(e)


def _str_call(function, *args, **kwargs):
	def iter_args():
		for i in args:
			yield _str_expr(i)
		
		for k, v in kwargs.items():
			if k.startswith('__'):
				k = '$' + k[2:]
			
			yield '{} = {}'.format(k, _str_expr(v))
	
	return '{}({})'.format(function, ', '.join(iter_args()))


@contextlib.contextmanager
def _write_file(path):
	temp_path = path + '~'
	
	os.makedirs(os.path.dirname(path), exist_ok = True)
	
	with open(temp_path, 'wb') as file:
		yield file
		
		file.flush()
		os.fsync(file.fileno())
	
	os.rename(temp_path, path)


def _singleton(cls):
	return cls()


def _tally(tuples):
	"""From an sequence of tuple, return a map from the first element of a tuple to a list of all the seconds elemnt of tuples with the same first element."""
	
	res = { }
	
	for k, v in tuples:
		list = res.get(k)
		
		if list is None:
			list = []
			
			res[k] = list
		
		list.append(v)
	
	return res


class Object(metaclass = abc.ABCMeta):
	def __init__(self, selections):
		self._selections = selections # Map from selector to selections. Must add up to the complete space. May contain void selections and traces of nuts.
	
	def __add__(self, other):
		return self.compose(operator.__add__, self, other)
	
	def __mul__(self, other):
		return self.compose(operator.__mul__, self, other)
	
	def __neg__(self):
		return self.compose(operator.__neg__, self)
	
	def __sub__(self, other):
		return self.compose(operator.__sub__, self, other)
	
	def _transform(self, text):
		return type(self)({ k: Selection.transform(text, v) for k, v in self._selections.items() })
	
	def move(self, offset = None, *, x = None, y = None, z = None):
		if offset is None:
			assert any(i is not None for i in [x, y, z])
			
			if x is None:
				x = 0
			
			if y is None:
				y = 0
			
			if z is None:
				z = 0
			
			offset = x, y, z
		else:
			assert isinstance(offset, tuple)
			assert len(offset) == 3
		
		assert all(isinstance(i, numbers.Real) for i in offset)
		
		return self._transform(_str_call('translate', offset))
	
	def scale(self, factor = None, *, x = None, y = None, z = None):
		if factor is None:
			assert any(i is not None for i in [x, y, z])
			
			if x is None:
				x = 1
			
			if y is None:
				y = 1
			
			if z is None:
				z = 1
			
			assert all(isinstance(i, numbers.Real) for i in [x, y, z])
			
			factor = x, y, z
		elif isinstance(factor, numbers.Real):
			factor = factor, factor, factor
		else:
			assert isinstance(factor, tuple)
			assert len(factor) == 3
		
		return self._transform(_str_call('scale', factor))
	
	def rotate(self, axis = None, angle = None, *, x = None, y = None, z = None):
		if axis is None:
			assert angle is None, 'axis and angle must be specified together.'
			
			for i in range(3):
				angle = [x, y, z][i]
				
				if angle is not None:
					assert all([x, y, z][j] is None for j in range(3) if j != i), 'Only one of x, y and z chan be specified.'
					
					axis = [1 if j == i else 0 for j in range(3)]
					
					break
		
		assert angle is not None, 'Neither angle nor any of x, y, z have been specified.'
		
		return self._transform(_str_call('rotate', angle / math.pi * 180, axis))
	
	def get_selection(self, selector):
		return self._selections.get(selector, void_selection)
	
	@property
	def selectors(self):
		return self._selections.keys()
	
	@classmethod
	def compose(cls, operation, *objects):
		assert callable(operation)
		assert all(isinstance(i, Object) for i in objects)
		
		def iter_selections():
			for selectors in itertools.product(*(i.selectors for i in objects)):
				selector = operation(*selectors)
				
				yield selector, [o.get_selection(s) for o, s in zip(objects, selectors)]

		groups_by_selector = _tally(iter_selections())
		
		def combine(groups):
			return Selection.union([Selection.intersect(i) for i in groups])
		
		def compute_selection(selector):
			groups = groups_by_selector[selector]
			inverse_groups = [i for s, g in groups_by_selector.items() if s != selector for i in g]
			
			# Use the conjunctive or disjunctive normal form, whichever has less terms.
			if len(groups) > len(inverse_groups):
				return Selection.invert(combine(inverse_groups))
			else:
				return combine(groups)
		
		return cls({ i: compute_selection(i) for i in groups_by_selector })
	
	@classmethod
	def create(cls, selection):
		"""Create a bipartite space, where True selects the given selection and False everything else."""
		
		return cls({ true_selector: selection, false_selector: Selection.invert(selection) })


class Selector(metaclass = abc.ABCMeta):
	@abc.abstractmethod
	def __bool__(self): pass
	
	@abc.abstractmethod
	def __add__(self, other): pass
	
	@abc.abstractmethod
	def __mul__(self, other): pass
	
	def __sub__(self, other):
		return self * -other
	
	def __radd__(self, other):
		return self + other
	
	def __rmul__(self, other):
		return self * other


@_singleton
class true_selector(Selector):
	def __bool__(self):
		return True
	
	def __add__(self, other):
		if other in [true_selector, false_selector]:
			return self
		else:
			return NotImplemented
	
	def __mul__(self, other):
		if other in [true_selector, false_selector]:
			return other
		else:
			return NotImplemented
	
	def __neg__(self):
		return false_selector


@_singleton
class false_selector(Selector):
	def __bool__(self):
		return False
	
	def __add__(self, other):
		if other in [true_selector, false_selector]:
			return other
		else:
			return NotImplemented
	
	def __mul__(self, other):
		if other in [true_selector, false_selector]:
			return self
		else:
			return NotImplemented
	
	def __neg__(self):
		return true_selector


def operation(operation):
	def fn(*objects):
		return Object.compose(operation, *objects)
	
	return fn


def union(object_seq):
	return functools.reduce(operator.__add__, object_seq, Object.create(void_selection))


def intersect(object_seq):
	return functools.reduce(operator.__mul__, object_seq, -Object.create(void_selection))


class Selection:
	@abc.abstractproperty
	def void(self): pass
	
	@abc.abstractproperty
	def node(self): pass
	
	@abc.abstractproperty
	def inverted(self): pass
	
	@classmethod
	def transform(cls, text, selection):
		if selection.void:
			return selection
		else:
			transformed_selection = NodeSelection(Node.compose(text, selection.node))
			
			if selection.inverted:
				return InvertedSelection(transformed_selection)
			else:
				return transformed_selection
	
	@classmethod
	def intersect(cls, selections):
		inverted_nodes = []
		nodes = []
		
		for i in selections:
			if i.inverted:
				# ignore inverted void selections
				if not i.void:
					inverted_nodes.append(i.node)
			else:
				if i.void:
					# If we intersect a non-inverted void selection the whole intersection will be void
					return void_selection
				else:
					nodes.append(i.node)
		
		if inverted_nodes:
			if nodes:
				return cls.create(Node.minus(Node.intersect(nodes), Node.union(inverted_nodes)))
			else:
				return cls.invert(cls.create(Node.union(inverted_nodes)))
		else:
			if nodes:
				return cls.create(Node.intersect(nodes))
			else:
				return void_selection
	
	@classmethod
	def union(cls, selections):
		return cls.invert(cls.intersect([cls.invert(i) for i in selections]))
	
	@classmethod
	def invert(cls, selection):
		return InvertedSelection(selection)
	
	@classmethod
	def create(cls, node):
		return NodeSelection(node)


@_singleton
class void_selection(Selection):
	def void(self):
		return True

	def node(self):
		assert False
	
	@property
	def inverted(self):
		return False


class NodeSelection(Selection):
	def __init__(self, node):
		self._node = node
	
	@property
	def void(self):
		return False

	@property
	def node(self):
		return self._node
	
	@property
	def inverted(self):
		return False


class InvertedSelection(Selection):
	def __init__(self, selection):
		assert isinstance(selection, Selection)
		
		self._selection = selection
	
	@property
	def void(self):
		return self._selection.void

	@property
	def node(self):
		return self._selection.node
	
	@property
	def inverted(self):
		return not self._selection.inverted


class Node:
	def __eq__(self, other):
		return self._compare_key == other._compare_key
	
	def __hash__(self):
		return hash(self._compare_key)
	
	@abc.abstractproperty
	def _compare_key(self): pass
	
	@abc.abstractproperty
	def child_nodes(self): pass
	
	@abc.abstractmethod
	def iter_lines(self, node_replacements): pass
	
	@classmethod
	def compose(cls, text, *nodes):
		return CompositeNode(text, nodes)
	
	@classmethod
	def intersect(cls, nodes):
		first, *rest = nodes
		
		if rest:
			return cls.compose(_str_call('intersection'), *nodes)
		else:
			return first
	
	@classmethod
	def union(cls, nodes):
		first, *rest = nodes
		
		if rest:
			return cls.compose(_str_call('union'), *nodes)
		else:
			return first
	
	@classmethod
	def minus(cls, left, right):
		return cls.compose(_str_call('difference'), left, right)
	
	@classmethod
	def create(cls, text):
		return PrimitiveNode(text)


class PrimitiveNode(Node):
	def __init__(self, text):
		self._text = text
	
	@property
	def _compare_key(self):
		return self._text
	
	@property
	def child_nodes(self):
		return []
	
	def iter_lines(self, node_replacements):
		yield self._text + ';'


class CompositeNode(Node):
	def __init__(self, text, nodes):
		assert all(isinstance(i, Node) for i in nodes)
		
		self._text = text
		self._nodes = nodes
	
	@property
	def _compare_key(self):
		return self._text, self._nodes
	
	@property
	def child_nodes(self):
		return self._nodes
	
	def iter_lines(self, node_replacements):
		def iter_node_lines(node):
			for j in node_replacements[node].iter_lines(node_replacements):
				yield '\t' + j
		
		first, *rest = self._nodes
		
		if rest:
			yield self._text + ' {'
			
			for i in self._nodes:
				yield from iter_node_lines(i)
			
			yield '}'
		else:
			yield self._text
			yield from iter_node_lines(first)


class _Module:
	def __init__(self, name, node):
		self._name = name
		self._node = node
	
	def iter_lines(self, node_replacements):
		yield 'module {}()'.format(self._name)
		
		for i in self._node.iter_lines(node_replacements):
			yield '\t' + i
	
	@property
	def reference(self):
		return Node.create(_str_call(self._name))


def compile_scad(object):
	"""Returns an interator of lines making up an OpenSCAD .scad file."""
	
	# Regardless of the type of seleectors used, select all parts that are "truthy"
	selection = Object.compose(lambda x: bool(x), object).get_selection(True)
	
	if selection.inverted:
		raise Exception('The top-level node is inverted.')
	
	if selection.void:
		raise Exception('The top-level node is void.')
	
	root_node = selection.node
	nodes_set = set() # All nodes in the project
	nodes_list = [] # All nodes ordered by their appearence. Nodes that depend on other nodes come before their dependees in this list.
	reused_nodes = set() # Nodes that are referenced by other nodes more than once.
	
	def walk_nodes(node):
		if node in nodes_set:
			reused_nodes.add(node)
		else:
			nodes_set.add(node)
			
			for i in node.child_nodes:
				walk_nodes(i)
			
			nodes_list.append(node)
	
	walk_nodes(root_node)
	
	node_replacements = { } # by actual node for all noces
	modules = [] # Modules for all nodes that are referenced more than once.
	
	# Iterate in serversed order so that nodes will be written to the file before their dependees.
	for i in reversed(nodes_list):
		if i in reused_nodes:
			module = _Module('node_{}'.format(len(modules) + 1), i)
			
			modules.append(module)
			replacement_node = module.reference
		else:
			replacement_node = i
		
		node_replacements[i] = replacement_node
	
	yield from root_node.iter_lines(node_replacements)
	
	for i in modules:
		yield '' # An empty line before each module definition
		yield from i.iter_lines(node_replacements)


def write_scad(object, path = None):
	if path is None:
		# noinspection PyUnresolvedReferences
		import __main__
		
		main_base_name_path, _ = os.path.splitext(__main__.__file__)
		path = main_base_name_path + '.scad'
	
	with _write_file(path) as file:
		for i in compile_scad(object):
			file.write((i + '\n').encode())


cube = Object.create(Selection.create(Node.create(_str_call('cube'))))
cylinder = Object.create(Selection.create(Node.create(_str_call('cylinder', __fn = 24))))
sphere = Object.create(Selection.create(Node.create(_str_call('sphere', __fn = 24))))
