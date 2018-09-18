# Copyright 2018 The TensorFlow Probability Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Tests for MaskedAutoregressiveFlow."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Dependency imports
import numpy as np
import tensorflow as tf
from tensorflow_probability.python import bijectors as tfb
from tensorflow_probability.python.internal import test_util
from tensorflow.python.ops.distributions import transformed_distribution as transformed_distribution_lib


class RealNVPTest(test_util.VectorDistributionTestHelpers, tf.test.TestCase):

  @property
  def _real_nvp_kwargs(self):
    return {
        "shift_and_log_scale_fn":
            tfb.real_nvp_default_template(hidden_layers=[3], shift_only=False),
        "is_constant_jacobian":
            False,
    }

  def testBijectorWithTrivialTransform(self):
    flat_x_ = np.random.normal(0., 1., 8).astype(np.float32)
    batched_x_ = np.random.normal(0., 1., (3, 8)).astype(np.float32)
    for x_ in [flat_x_, batched_x_]:
      nvp = tfb.RealNVP(
          num_masked=4,
          validate_args=True,
          shift_and_log_scale_fn=lambda x, _: (x, x),
          is_constant_jacobian=False)
      x = tf.constant(x_)
      forward_x = nvp.forward(x)
      # Use identity to invalidate cache.
      inverse_y = nvp.inverse(tf.identity(forward_x))
      forward_inverse_y = nvp.forward(inverse_y)
      fldj = nvp.forward_log_det_jacobian(x, event_ndims=1)
      # Use identity to invalidate cache.
      ildj = nvp.inverse_log_det_jacobian(tf.identity(forward_x), event_ndims=1)
      forward_x_ = self.evaluate(forward_x)
      inverse_y_ = self.evaluate(inverse_y)
      forward_inverse_y_ = self.evaluate(forward_inverse_y)
      ildj_ = self.evaluate(ildj)
      fldj_ = self.evaluate(fldj)

      self.assertEqual("real_nvp", nvp.name)
      self.assertAllClose(forward_x_, forward_inverse_y_, rtol=1e-4, atol=0.)
      self.assertAllClose(x_, inverse_y_, rtol=1e-4, atol=0.)
      self.assertAllClose(ildj_, -fldj_, rtol=1e-6, atol=0.)

  def testBatchedBijectorWithMLPTransform(self):
    x_ = np.random.normal(0., 1., (3, 8)).astype(np.float32)
    with self.test_session() as sess:
      nvp = tfb.RealNVP(
          num_masked=4, validate_args=True, **self._real_nvp_kwargs)
      x = tf.constant(x_)
      forward_x = nvp.forward(x)
      # Use identity to invalidate cache.
      inverse_y = nvp.inverse(tf.identity(forward_x))
      forward_inverse_y = nvp.forward(inverse_y)
      fldj = nvp.forward_log_det_jacobian(x, event_ndims=1)
      # Use identity to invalidate cache.
      ildj = nvp.inverse_log_det_jacobian(tf.identity(forward_x), event_ndims=1)
      tf.global_variables_initializer().run()
      [
          forward_x_,
          inverse_y_,
          forward_inverse_y_,
          ildj_,
          fldj_,
      ] = sess.run([
          forward_x,
          inverse_y,
          forward_inverse_y,
          ildj,
          fldj,
      ])
      self.assertEqual("real_nvp", nvp.name)
      self.assertAllClose(forward_x_, forward_inverse_y_, rtol=1e-4, atol=0.)
      self.assertAllClose(x_, inverse_y_, rtol=1e-4, atol=0.)
      self.assertAllClose(ildj_, -fldj_, rtol=1e-6, atol=0.)

  def testBijectorConditionKwargs(self):
    batch_size = 3
    x_ = np.arange(batch_size * 4 * 2).astype(np.float32).reshape(
        batch_size, 4 * 2)
    conditions = {
        "a":
        tf.reshape(
            tf.range(batch_size * 4, dtype=tf.float32), (batch_size, 4)),
        "b":
        tf.reshape(
            tf.range(batch_size * 2, dtype=tf.float32), (batch_size, 2)),
    }

    nvp = tfb.RealNVP(
        num_masked=4, validate_args=True, **self._real_nvp_kwargs)
    x = tf.constant(x_)

    forward_x = nvp.forward(x, **conditions)
    # Use identity to invalidate cache.
    inverse_y = nvp.inverse(tf.identity(forward_x), **conditions)
    forward_inverse_y = nvp.forward(inverse_y, **conditions)
    fldj = nvp.forward_log_det_jacobian(x, event_ndims=1, **conditions)
    # Use identity to invalidate cache.
    ildj = nvp.inverse_log_det_jacobian(
        tf.identity(forward_x), event_ndims=1, **conditions)
    self.evaluate(tf.global_variables_initializer())
    [
        forward_x_,
        inverse_y_,
        forward_inverse_y_,
        ildj_,
        fldj_,
    ] = self.evaluate([
        forward_x,
        inverse_y,
        forward_inverse_y,
        ildj,
        fldj,
    ])
    self.assertEqual("real_nvp", nvp.name)
    self.assertAllClose(forward_x_, forward_inverse_y_, rtol=1e-6)
    self.assertAllClose(x_, inverse_y_, rtol=1e-6)
    self.assertAllClose(ildj_, -fldj_, rtol=1e-6)

  def testMutuallyConsistent(self):
    dims = 4
    with self.test_session() as sess:
      nvp = tfb.RealNVP(
          num_masked=3, validate_args=True, **self._real_nvp_kwargs)
      dist = transformed_distribution_lib.TransformedDistribution(
          distribution=tf.distributions.Normal(loc=0., scale=1.),
          bijector=nvp,
          event_shape=[dims],
          validate_args=True)
      self.run_test_sample_consistent_log_prob(
          sess_run_fn=sess.run,
          dist=dist,
          num_samples=int(1e5),
          radius=1.,
          center=0.,
          rtol=0.02)

  def testInvertMutuallyConsistent(self):
    dims = 4
    with self.test_session() as sess:
      nvp = tfb.Invert(
          tfb.RealNVP(
              num_masked=3, validate_args=True, **self._real_nvp_kwargs))
      dist = transformed_distribution_lib.TransformedDistribution(
          distribution=tf.distributions.Normal(loc=0., scale=1.),
          bijector=nvp,
          event_shape=[dims],
          validate_args=True)
      self.run_test_sample_consistent_log_prob(
          sess_run_fn=sess.run,
          dist=dist,
          num_samples=int(1e5),
          radius=1.,
          center=0.,
          rtol=0.02)


class NICETest(RealNVPTest):

  @property
  def _real_nvp_kwargs(self):
    return {
        "shift_and_log_scale_fn":
            tfb.real_nvp_default_template(hidden_layers=[2], shift_only=True),
        "is_constant_jacobian":
            True,
    }


class RealNVPConstantShiftScaleTest(RealNVPTest):

  @property
  def _real_nvp_kwargs(self):

    def constant_shift_log_scale_fn(x0, output_units, **condition_kwargs):
      del x0, output_units, condition_kwargs
      shift = tf.constant([0.1])
      log_scale = tf.constant([0.5])
      return shift, log_scale

    return {
        "shift_and_log_scale_fn": constant_shift_log_scale_fn,
        "is_constant_jacobian": True,
    }

if __name__ == "__main__":
  tf.test.main()
