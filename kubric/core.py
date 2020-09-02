# Copyright 2020 The Kubric Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import uuid
from collections import defaultdict

import traitlets as tl
import mathutils
from traitlets import default, validate

import kubric.traits as kt
from kubric.color import Color


class Asset(tl.HasTraits):
  uid = tl.Unicode(read_only=True)

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.destruction_callbacks = []
    self.keyframe_callbacks = []
    self.keyframes = defaultdict(dict)

  @default('uid')
  def _uid(self):
    return str(uuid.uuid4())

  def keyframe_insert(self, member: str, frame: int):
    if not self.has_trait(member):
      raise KeyError('Unknown member "{}".'.format(member))
    self.keyframes[member][frame] = getattr(self, member)
    for func in self.keyframe_callbacks:
      func(owner=self, member=member, frame=frame)

  def __hash__(self):
    return object.__hash__(self)

  def __eq__(self, other):
    return id(self) == id(other)

  def __del__(self):
    for func in self.destruction_callbacks:
      func(owner=self)


# ## ### ####  Materials  #### ### ## #

class Material(Asset):
  pass


class PrincipledBSDFMaterial(Material):
  """A physically based material suited for uniform colored plastic, rubber, metal, glass, etc..."""
  color = kt.RGBA(default_value=Color.from_name('white'))
  metallic = tl.Float(0.)
  specular = tl.Float(0.5)
  specular_tint = tl.Float(0.)
  roughness = tl.Float(0.4)
  ior = tl.Float(1.45)
  transmission = tl.Float(0)
  transmission_roughness = tl.Float(0)
  emission = kt.RGBA(default_value=Color.from_name('black'))


class FlatMaterial(Material):
  """Renders the object as a uniform color without any shading.
  If holdout is true, then the pixels of the object will be transparent in the final image (alpha=0).
  (Note, that this is not the same as a transparent object. It still "occludes" other objects)

  The indirect_visibility flag controls if the object casts shadows, can be seen in reflections and
  emits light.
  """
  color = kt.RGBA(default_value=Color.from_name('white'))
  holdout = tl.Bool(False)
  indirect_visibility = tl.Bool(True)


class MeshChromeMaterial(Material):
  color = kt.RGBA(default_value=Color.from_name('white'))
  roughness = tl.Float(0.4)




# ## ### ####  3D Objects  #### ### ## #


class Object3D(Asset):
  position = kt.Vector3D(default_value=(0., 0., 0.))
  quaternion = kt.Quaternion()
  scale = kt.Vector3D(default_value=(1., 1., 1.))

  up = tl.CaselessStrEnum(['X', 'Y', 'Z', '-X', '-Y', '-Z'], default_value='Y')
  front = tl.CaselessStrEnum(['X', 'Y', 'Z', '-X', '-Y', '-Z'], default_value='-Z')

  def look_at(self, target):
    direction = mathutils.Vector(target) - mathutils.Vector(self.position)
    self.quaternion = direction.to_track_quat(self.front.upper(), self.up.upper())


class PhysicalObject(Object3D):
  velocity = kt.Vector3D(default_value=(0., 0., 0.))
  angular_velocity = kt.Vector3D(default_value=(0., 0., 0.))

  static = tl.Bool(False)
  mass = tl.Float(1.0)
  friction = tl.Float(0.0)
  restitution = tl.Float(0.5)

  bounds = tl.Tuple(kt.Vector3D(), kt.Vector3D(),
                    default_value=((0., 0., 0.), (0., 0, 0.)))

  center_mesh = tl.Bool(False)

  @validate('mass')
  def _valid_mass(self, proposal):
    mass = proposal['value']
    if mass < 0:
      raise tl.TraitError(f'mass cannot be negative ({mass})')
    return mass

  @validate('friction')
  def _valid_friction(self, proposal):
    friction = proposal['value']
    if friction < 0:
      raise tl.TraitError(f'friction cannot be negative ({friction})')
    return friction

  @validate('friction')
  def _valid_friction(self, proposal):
    friction = proposal['value']
    if friction < 0:
      raise tl.TraitError(f'friction cannot be negative ({friction})')
    return friction

  @validate('bounds')
  def _valid_bounds(self, proposal):
    lower, upper = proposal['value']
    for l, u in zip(lower, upper):
      if l > u:
        raise tl.TraitError(f'lower bound cannot be larger than upper bound ({lower} !<= {upper})')
    return lower, upper


class Cube(PhysicalObject):
  material = tl.Instance(Material, allow_none=True, default_value=None)


class Sphere(PhysicalObject):
  material = tl.Instance(Material, allow_none=True, default_value=None)


class FileBasedObject(PhysicalObject):
  asset_id = tl.Unicode()

  simulation_filename = tl.Unicode()   # TODO: use pathlib.Path instead
  render_filename = tl.Unicode()       # TODO: use pathlib.Path instead

  material = tl.Instance(Material, allow_none=True, default_value=None)


# ## ### ####  Lights  #### ### ## #

class Light(Object3D):
  color = kt.RGB(default_value=Color.from_name('white').rgb)
  intensity = tl.Float(1.)


class DirectionalLight(Light):
  shadow_softness = tl.Float(0.2)


class RectAreaLight(Light):
  width = tl.Float(1)
  height = tl.Float(1)


class PointLight(Light):
  pass


# ## ### ####  Cameras  #### ### ## #

class Camera(Object3D):
  pass


class PerspectiveCamera(Camera):
  focal_length = tl.Float(50)
  sensor_width = tl.Float(36)


class OrthographicCamera(Camera):
  pass


# ## ### ####  Scene  #### ### ## #

class Scene(Asset):
  frame_start = tl.Integer(0)
  frame_end = tl.Integer(48)

  frame_rate = tl.Integer(24)
  step_rate = tl.Integer(240)

  camera = tl.Instance(Camera, allow_none=True, default_value=None)
  resolution = tl.Tuple(tl.Integer(), tl.Integer(), default_value=(512, 512))

  gravity = kt.Vector3D(default_value=(0, 0, -10.))


class AttributeSetter:
  def __init__(self, target_obj, target_name, ignore_none=True):
    self.target_name = target_name
    self.target_obj = target_obj
    self.ignore_none = ignore_none
    self.mapping = None  # has to be set by the add() function

  def __call__(self, change):
    if isinstance(self.target_name, (list, tuple)):
      for name, val in zip(self.target_name, change.new):
        self._set(name, val)
    else:
      self._set(self.target_name, change.new)

  def _set(self, name, value):
    if value is None and self.ignore_none:
      return
    if isinstance(value, Asset):
      value = self.mapping[value]  # convert kubric objects to blender objects before assigning
    setattr(self.target_obj, name, value)

