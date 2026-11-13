API reference
=============

.. module:: deltakit_maestro

Everything below imports from ``deltakit_maestro``. Most code needs only
:class:`MaestroBackend`; the :doc:`guide` explains how it runs each circuit.

Backend
-------

.. autoclass:: MaestroBackend

   .. automethod:: simulate
   .. automethod:: compile_sampler
   .. automethod:: as_sinter_task
   .. automethod:: sinter_decoders
   .. automethod:: twirled_circuit
   .. automethod:: config_for

.. autoclass:: SimulationResult
   :members: num_measurements

.. data:: SINTER_DECODER
   :value: 'maestro'

   The decoder name that :meth:`MaestroBackend.as_sinter_task` gives its tasks.
   :meth:`MaestroBackend.sinter_decoders` maps it to the Maestro sampler.

Noise translation
-----------------

The steps :class:`MaestroBackend` takes with a noisy circuit, for using them
directly. The guide's :doc:`guide/noise` page explains them.

.. autofunction:: to_stim
.. autofunction:: noise_params_from_stim
.. autofunction:: strip_gate_noise
.. autofunction:: build_noise_model
.. autofunction:: pauli_twirl_circuit

.. data:: NOISE_TYPES
   :value: ('pauli', 'coherent', 'full', 'none')

   The values ``noise_type`` takes.

.. data:: NOISE_KEYS
   :value: ('p_1q', 'p_2q', 'readout_error', 't1', 'coherent')

   The noise keywords that override or extend the rates read from a circuit.
