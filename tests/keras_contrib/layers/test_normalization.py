import pytest
import numpy as np
from numpy.testing import assert_allclose

from keras.layers import Dense, Activation, Input
from keras import regularizers
from keras.utils.test_utils import layer_test
from keras_contrib.layers import normalization
from keras.models import Sequential, Model
from keras import backend as K
from keras_contrib import backend as KC

input_1 = np.arange(10)
input_2 = np.zeros(10)
input_3 = np.ones((10))
input_shapes = [np.ones((10, 10)), np.ones((10, 10, 10))]


def basic_instancenorm_test():
    from keras import regularizers
    layer_test(normalization.InstanceNormalization,
               kwargs={'epsilon': 0.1,
                       'gamma_regularizer': regularizers.l2(0.01),
                       'beta_regularizer': regularizers.l2(0.01)},
               input_shape=(3, 4, 2))
    layer_test(normalization.InstanceNormalization,
               kwargs={'gamma_initializer': 'ones',
                       'beta_initializer': 'ones'},
               input_shape=(3, 4, 2))
    layer_test(normalization.InstanceNormalization,
               kwargs={'scale': False, 'center': False},
               input_shape=(3, 3))


def test_instancenorm_correctness_rank2():
    model = Sequential()
    norm = normalization.InstanceNormalization(input_shape=(10, 1), axis=-1)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10, 1))
    model.fit(x, x, epochs=4, verbose=0)
    out = model.predict(x)
    out -= K.eval(norm.beta)
    out /= K.eval(norm.gamma)

    assert_allclose(out.mean(), 0.0, atol=1e-1)
    assert_allclose(out.std(), 1.0, atol=1e-1)


def test_instancenorm_correctness_rank1():
    # make sure it works with rank1 input tensor (batched)
    model = Sequential()
    norm = normalization.InstanceNormalization(input_shape=(10,), axis=None)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10))
    model.fit(x, x, epochs=4, verbose=0)
    out = model.predict(x)
    out -= K.eval(norm.beta)
    out /= K.eval(norm.gamma)

    assert_allclose(out.mean(), 0.0, atol=1e-1)
    assert_allclose(out.std(), 1.0, atol=1e-1)


def test_instancenorm_training_argument():
    bn1 = normalization.InstanceNormalization(input_shape=(10,))
    x1 = Input(shape=(10,))
    y1 = bn1(x1, training=True)

    model1 = Model(x1, y1)
    np.random.seed(123)
    x = np.random.normal(loc=5.0, scale=10.0, size=(20, 10))
    output_a = model1.predict(x)

    model1.compile(loss='mse', optimizer='rmsprop')
    model1.fit(x, x, epochs=1, verbose=0)
    output_b = model1.predict(x)
    assert np.abs(np.sum(output_a - output_b)) > 0.1
    assert_allclose(output_b.mean(), 0.0, atol=1e-1)
    assert_allclose(output_b.std(), 1.0, atol=1e-1)

    bn2 = normalization.InstanceNormalization(input_shape=(10,))
    x2 = Input(shape=(10,))
    bn2(x2, training=False)


def test_instancenorm_convnet():
    model = Sequential()
    norm = normalization.InstanceNormalization(axis=1, input_shape=(3, 4, 4))
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 3, 4, 4))
    model.fit(x, x, epochs=4, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm.beta), (1, 3, 1, 1))
    out /= np.reshape(K.eval(norm.gamma), (1, 3, 1, 1))

    assert_allclose(np.mean(out, axis=(0, 2, 3)), 0.0, atol=1e-1)
    assert_allclose(np.std(out, axis=(0, 2, 3)), 1.0, atol=1e-1)


def test_shared_instancenorm():
    '''Test that a IN layer can be shared
    across different data streams.
    '''
    # Test single layer reuse
    bn = normalization.InstanceNormalization(input_shape=(10,))
    x1 = Input(shape=(10,))
    bn(x1)

    x2 = Input(shape=(10,))
    y2 = bn(x2)

    x = np.random.normal(loc=5.0, scale=10.0, size=(2, 10))
    model = Model(x2, y2)
    model.compile('sgd', 'mse')
    model.train_on_batch(x, x)

    # Test model-level reuse
    x3 = Input(shape=(10,))
    y3 = model(x3)
    new_model = Model(x3, y3)
    new_model.compile('sgd', 'mse')
    new_model.train_on_batch(x, x)


def test_instancenorm_perinstancecorrectness():
    model = Sequential()
    norm = normalization.InstanceNormalization(input_shape=(10,))
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # bimodal distribution
    z = np.random.normal(loc=5.0, scale=10.0, size=(2, 10))
    y = np.random.normal(loc=-5.0, scale=17.0, size=(2, 10))
    x = np.append(z, y)
    x = np.reshape(x, (4, 10))
    model.fit(x, x, epochs=4, batch_size=4, verbose=1)
    out = model.predict(x)
    out -= K.eval(norm.beta)
    out /= K.eval(norm.gamma)

    # verify that each instance in the batch is individually normalized
    for i in range(4):
        instance = out[i]
        assert_allclose(instance.mean(), 0.0, atol=1e-1)
        assert_allclose(instance.std(), 1.0, atol=1e-1)

    # if each instance is normalized, so should the batch
    assert_allclose(out.mean(), 0.0, atol=1e-1)
    assert_allclose(out.std(), 1.0, atol=1e-1)


def test_instancenorm_perchannel_correctness():

    # have each channel with a different average and std
    x = np.random.normal(loc=5.0, scale=2.0, size=(10, 1, 4, 4))
    y = np.random.normal(loc=10.0, scale=3.0, size=(10, 1, 4, 4))
    z = np.random.normal(loc=-5.0, scale=5.0, size=(10, 1, 4, 4))

    batch = np.append(x, y, axis=1)
    batch = np.append(batch, z, axis=1)

    # this model does not provide a normalization axis
    model = Sequential()
    norm = normalization.InstanceNormalization(axis=None, input_shape=(3, 4, 4), center=False, scale=False)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')
    model.fit(batch, batch, epochs=4, verbose=0)
    out = model.predict(batch)

    # values will not be normalized per-channel
    for instance in range(10):
        for channel in range(3):
            activations = out[instance, channel]
            assert abs(activations.mean()) > 1e-2
            assert abs(activations.std() - 1.0) > 1e-6

        # but values are still normalized per-instance
        activations = out[instance]
        assert_allclose(activations.mean(), 0.0, atol=1e-1)
        assert_allclose(activations.std(), 1.0, atol=1e-1)

    # this model sets the channel as a normalization axis
    model = Sequential()
    norm = normalization.InstanceNormalization(axis=1, input_shape=(3, 4, 4), center=False, scale=False)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    model.fit(batch, batch, epochs=4, verbose=0)
    out = model.predict(batch)

    # values are now normalized per-channel
    for instance in range(10):
        for channel in range(3):
            activations = out[instance, channel]
            assert_allclose(activations.mean(), 0.0, atol=1e-1)
            assert_allclose(activations.std(), 1.0, atol=1e-1)


def basic_batchrenorm_test():
    from keras import regularizers

    layer_test(normalization.BatchRenormalization,
               input_shape=(3, 4, 2))

    layer_test(normalization.BatchRenormalization,
               kwargs={'gamma_regularizer': regularizers.l2(0.01),
                       'beta_regularizer': regularizers.l2(0.01)},
               input_shape=(3, 4, 2))


def test_batchrenorm_mode_0_or_2():
    for training in [1, 0, None]:
        ip = Input(shape=(10,))
        norm_m0 = normalization.BatchRenormalization(momentum=0.8)
        out = norm_m0(ip, training=training)
        model = Model(ip, out)
        model.compile(loss='mse', optimizer='sgd')

        # centered on 5.0, variance 10.0
        X = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10))
        model.fit(X, X, epochs=4, verbose=0)
        out = model.predict(X)
        out -= K.eval(norm_m0.beta)
        out /= K.eval(norm_m0.gamma)

        assert_allclose(out.mean(), 0.0, atol=1e-1)
        assert_allclose(out.std(), 1.0, atol=1e-1)


@pytest.mark.skipif(K.backend() == 'tensorflow',
                    reason='There is a bug with the tensorflow backend when'
                           'axis is something else than -1.')
def test_batchrenorm_mode_0_or_2_twice():
    # This is a regression test for issue #4881 with the old
    # batch normalization functions in the Theano backend.
    model = Sequential()
    model.add(normalization.BatchRenormalization(input_shape=(10, 5, 5), axis=1))
    model.add(normalization.BatchRenormalization(input_shape=(10, 5, 5), axis=1))
    model.compile(loss='mse', optimizer='sgd')

    X = np.random.normal(loc=5.0, scale=10.0, size=(20, 10, 5, 5))
    model.fit(X, X, epochs=1, verbose=0)
    model.predict(X)


@pytest.mark.skipif(K.backend() == 'tensorflow',
                    reason='There is a bug with the tensorflow backend when'
                           'axis is something else than -1.')
def test_batchrenorm_mode_0_convnet():
    model = Sequential()
    norm_m0 = normalization.BatchRenormalization(axis=1, input_shape=(3, 4, 4), momentum=0.8)
    model.add(norm_m0)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    X = np.random.normal(loc=5.0, scale=10.0, size=(1000, 3, 4, 4))
    model.fit(X, X, epochs=4, verbose=0)
    out = model.predict(X)
    out -= np.reshape(K.eval(norm_m0.beta), (1, 3, 1, 1))
    out /= np.reshape(K.eval(norm_m0.gamma), (1, 3, 1, 1))

    assert_allclose(np.mean(out, axis=(0, 2, 3)), 0.0, atol=1e-1)
    assert_allclose(np.std(out, axis=(0, 2, 3)), 1.0, atol=1e-1)


def test_shared_batchrenorm():
    '''Test that a BN layer can be shared
    across different data streams.
    '''
    # Test single layer reuse
    bn = normalization.BatchRenormalization(input_shape=(10,))
    x1 = Input(shape=(10,))
    bn(x1)

    x2 = Input(shape=(10,))
    y2 = bn(x2)

    x = np.random.normal(loc=5.0, scale=10.0, size=(2, 10))
    model = Model(x2, y2)
    assert len(model.updates) == 5
    model.compile('sgd', 'mse')
    model.train_on_batch(x, x)

    # Test model-level reuse
    x3 = Input(shape=(10,))
    y3 = model(x3)
    new_model = Model(x3, y3)
    assert len(model.updates) == 5
    new_model.compile('sgd', 'mse')
    new_model.train_on_batch(x, x)


def test_batchrenorm_clipping_schedule():
    '''Test that the clipping schedule isn't fixed at r_max=1, d_max=0'''
    inp = Input(shape=(10,))
    bn = normalization.BatchRenormalization(t_delta=1.)
    out = bn(inp)
    model = Model(inp, out)
    model.compile('sgd', 'mse')

    x = np.random.normal(5, 10, size=(2, 10))
    y = np.random.normal(5, 10, size=(2, 10))

    r_max, d_max = K.get_value(bn.r_max), K.get_value(bn.d_max)
    assert r_max == 1
    assert d_max == 0

    for i in range(10):
        model.train_on_batch(x, y)

    r_max, d_max = K.get_value(bn.r_max), K.get_value(bn.d_max)
    assert_allclose([r_max, d_max], [3, 5], atol=1e-1)


def test_batchrenorm_get_config():
    '''Test that get_config works on a model with a batchrenorm layer.'''
    x = Input(shape=(10,))
    y = normalization.BatchRenormalization()(x)
    model = Model(x, y)
    model.get_config()


def test_basic_groupnorm():
    layer_test(normalization.GroupNormalization,
               kwargs={'groups': 2,
                       'epsilon': 0.1,
                       'gamma_regularizer': regularizers.l2(0.01),
                       'beta_regularizer': regularizers.l2(0.01)},
               input_shape=(3, 4, 2))
    layer_test(normalization.GroupNormalization,
               kwargs={'groups': 2,
                       'epsilon': 0.1,
                       'axis': 1},
               input_shape=(3, 4, 2))
    layer_test(normalization.GroupNormalization,
               kwargs={'groups': 2,
                       'gamma_initializer': 'ones',
                       'beta_initializer': 'ones'},
               input_shape=(3, 4, 2, 4))
    if K.backend() != 'theano':
        layer_test(normalization.GroupNormalization,
                   kwargs={'groups': 2,
                           'axis': 1,
                           'scale': False,
                           'center': False},
                   input_shape=(3, 4, 2, 4))


def test_groupnorm_correctness_1d():
    model = Sequential()
    norm = normalization.GroupNormalization(input_shape=(10,), groups=2)
    model.add(norm)
    model.compile(loss='mse', optimizer='rmsprop')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10))
    model.fit(x, x, epochs=5, verbose=0)
    out = model.predict(x)
    out -= K.eval(norm.beta)
    out /= K.eval(norm.gamma)

    assert_allclose(out.mean(), 0.0, atol=1e-1)
    assert_allclose(out.std(), 1.0, atol=1e-1)


def test_groupnorm_correctness_2d():
    model = Sequential()
    norm = normalization.GroupNormalization(axis=1, input_shape=(10, 6), groups=2)
    model.add(norm)
    model.compile(loss='mse', optimizer='rmsprop')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10, 6))
    model.fit(x, x, epochs=5, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm.beta), (1, 10, 1))
    out /= np.reshape(K.eval(norm.gamma), (1, 10, 1))

    assert_allclose(out.mean(axis=(0, 2)), 0.0, atol=1.1e-1)
    assert_allclose(out.std(axis=(0, 2)), 1.0, atol=1.1e-1)


def test_groupnorm_correctness_2d_different_groups():
    norm1 = normalization.GroupNormalization(axis=1, input_shape=(10, 6), groups=2)
    norm2 = normalization.GroupNormalization(axis=1, input_shape=(10, 6), groups=1)
    norm3 = normalization.GroupNormalization(axis=1, input_shape=(10, 6), groups=10)

    model = Sequential()
    model.add(norm1)
    model.compile(loss='mse', optimizer='rmsprop')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10, 6))
    model.fit(x, x, epochs=5, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm1.beta), (1, 10, 1))
    out /= np.reshape(K.eval(norm1.gamma), (1, 10, 1))

    assert_allclose(out.mean(axis=(0, 2)), 0.0, atol=1.1e-1)
    assert_allclose(out.std(axis=(0, 2)), 1.0, atol=1.1e-1)

    model = Sequential()
    model.add(norm2)
    model.compile(loss='mse', optimizer='rmsprop')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10, 6))
    model.fit(x, x, epochs=5, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm2.beta), (1, 10, 1))
    out /= np.reshape(K.eval(norm2.gamma), (1, 10, 1))

    assert_allclose(out.mean(axis=(0, 2)), 0.0, atol=1.1e-1)
    assert_allclose(out.std(axis=(0, 2)), 1.0, atol=1.1e-1)

    model = Sequential()
    model.add(norm3)
    model.compile(loss='mse', optimizer='rmsprop')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 10, 6))
    model.fit(x, x, epochs=5, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm3.beta), (1, 10, 1))
    out /= np.reshape(K.eval(norm3.gamma), (1, 10, 1))

    assert_allclose(out.mean(axis=(0, 2)), 0.0, atol=1.1e-1)
    assert_allclose(out.std(axis=(0, 2)), 1.0, atol=1.1e-1)


def test_groupnorm_mode_twice():
    # This is a regression test for issue #4881 with the old
    # batch normalization functions in the Theano backend.
    model = Sequential()
    model.add(normalization.GroupNormalization(input_shape=(10, 5, 5), axis=1, groups=2))
    model.add(normalization.GroupNormalization(input_shape=(10, 5, 5), axis=1, groups=2))
    model.compile(loss='mse', optimizer='sgd')

    x = np.random.normal(loc=5.0, scale=10.0, size=(20, 10, 5, 5))
    model.fit(x, x, epochs=1, verbose=0)
    model.predict(x)


def test_groupnorm_convnet():
    model = Sequential()
    norm = normalization.GroupNormalization(axis=1, input_shape=(3, 4, 4), groups=3)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 3, 4, 4))
    model.fit(x, x, epochs=4, verbose=0)
    out = model.predict(x)
    out -= np.reshape(K.eval(norm.beta), (1, 3, 1, 1))
    out /= np.reshape(K.eval(norm.gamma), (1, 3, 1, 1))

    assert_allclose(np.mean(out, axis=(0, 2, 3)), 0.0, atol=1e-1)
    assert_allclose(np.std(out, axis=(0, 2, 3)), 1.0, atol=1e-1)


@pytest.mark.skipif((K.backend() == 'theano'),
                    reason='Bug with theano backend')
def test_groupnorm_convnet_no_center_no_scale():
    model = Sequential()
    norm = normalization.GroupNormalization(axis=-1, center=False, scale=False,
                                            input_shape=(3, 4, 4), groups=2)
    model.add(norm)
    model.compile(loss='mse', optimizer='sgd')

    # centered on 5.0, variance 10.0
    x = np.random.normal(loc=5.0, scale=10.0, size=(1000, 3, 4, 4))
    model.fit(x, x, epochs=4, verbose=0)
    out = model.predict(x)

    assert_allclose(np.mean(out, axis=(0, 2, 3)), 0.0, atol=1e-1)
    assert_allclose(np.std(out, axis=(0, 2, 3)), 1.0, atol=1e-1)


def test_shared_groupnorm():
    '''Test that a GN layer can be shared
    across different data streams.
    '''
    # Test single layer reuse
    bn = normalization.GroupNormalization(input_shape=(10,), groups=2)
    x1 = Input(shape=(10,))
    bn(x1)

    x2 = Input(shape=(10,))
    y2 = bn(x2)

    x = np.random.normal(loc=5.0, scale=10.0, size=(2, 10))
    model = Model(x2, y2)
    assert len(model.updates) == 0
    model.compile('sgd', 'mse')
    model.train_on_batch(x, x)

    # Test model-level reuse
    x3 = Input(shape=(10,))
    y3 = model(x3)
    new_model = Model(x3, y3)
    assert len(model.updates) == 0
    new_model.compile('sgd', 'mse')
    new_model.train_on_batch(x, x)


def test_that_trainable_disables_updates():
    val_a = np.random.random((10, 4))
    val_out = np.random.random((10, 4))

    a = Input(shape=(4,))
    layer = normalization.GroupNormalization(input_shape=(4,), groups=2)
    b = layer(a)
    model = Model(a, b)

    model.trainable = False
    assert len(model.updates) == 0

    model.compile('sgd', 'mse')
    assert len(model.updates) == 0

    x1 = model.predict(val_a)
    model.train_on_batch(val_a, val_out)
    x2 = model.predict(val_a)
    assert_allclose(x1, x2, atol=1e-7)

    model.trainable = True
    model.compile('sgd', 'mse')
    assert len(model.updates) == 0

    model.train_on_batch(val_a, val_out)
    x2 = model.predict(val_a)
    assert np.abs(np.sum(x1 - x2)) > 1e-5

    layer.trainable = False
    model.compile('sgd', 'mse')
    assert len(model.updates) == 0

    x1 = model.predict(val_a)
    model.train_on_batch(val_a, val_out)
    x2 = model.predict(val_a)
    assert_allclose(x1, x2, atol=1e-7)


if __name__ == '__main__':
    pytest.main([__file__])
