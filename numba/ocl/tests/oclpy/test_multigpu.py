from numba import ocl
import numpy as np
from numba import unittest_support as unittest
from numba.ocl.testing import OCLTestCase
import threading


class TestMultiGPUContext(OCLTestCase):
    @unittest.skipIf(len(ocl.gpus) < 2, "need more than 1 gpus")
    def test_multigpu_context(self):
        @ocl.jit("void(float64[:], float64[:])")
        def copy_plus_1(inp, out):
            i = ocl.get_global_id(0)
            if i < out.size:
                out[i] = inp[i] + 1

        def check(inp, out):
            np.testing.assert_equal(inp + 1, out)


        N = 32
        A = np.arange(N, dtype=np.float64)
        B = np.arange(N, dtype=np.float64)

        with ocl.gpus[0]:
            copy_plus_1[1, N](A, B)

        check(A, B)

        copy_plus_1[1, N](A, B)
        check(A, B)

        with ocl.gpus[0]:
            A0 = np.arange(N, dtype=np.float64)
            B0 = np.arange(N, dtype=np.float64)
            copy_plus_1[1, N](A0, B0)

            with ocl.gpus[1]:
                A1 = np.arange(N, dtype=np.float64)
                B1 = np.arange(N, dtype=np.float64)
                copy_plus_1[1, N](A1, B1)

        check(A0, B0)
        check(A1, B1)

        A = np.arange(N, dtype=np.float64)
        B = np.arange(N, dtype=np.float64)
        copy_plus_1[1, N](A, B)
        check(A, B)

    def test_multithreaded(self):
        def work(gpu, dA, results, ridx):
            try:
                with gpu:
                    arr = dA.copy_to_host()

            except BaseException as e:
                results[ridx] = e

            else:
                results[ridx] = np.all(arr == np.arange(10))


        dA = ocl.to_device(np.arange(10))

        nthreads = 10
        results = [None] * nthreads
        threads = [threading.Thread(target=work, args=(ocl.gpus.current,
                                                       dA, results, i))
                   for i in range(nthreads)]
        for th in threads:
            th.start()

        for th in threads:
            th.join()

        for r in results:
            if isinstance(r, BaseException):
                raise r
            else:
                self.assertTrue(r)


    @unittest.skipIf(len(ocl.gpus) < 2, "need more than 1 gpus")
    def test_with_context(self):

        @ocl.jit
        def vector_add_scalar(arr, val):
            i = ocl.get_global_id(0)
            if i < arr.size:
                arr[i] += val


        hostarr = np.arange(10, dtype=np.float32)
        with ocl.gpus[0]:
            arr1 = ocl.to_device(hostarr)

        with ocl.gpus[1]:
            arr2 = ocl.to_device(hostarr)

        with ocl.gpus[0]:
            vector_add_scalar[1, 10](arr1, 1)

        with ocl.gpus[1]:
            vector_add_scalar[1, 10](arr2, 2)

        with ocl.gpus[0]:
            np.testing.assert_equal(arr1.copy_to_host(), (hostarr + 1))

        with ocl.gpus[1]:
            np.testing.assert_equal(arr2.copy_to_host(), (hostarr + 2))

        with ocl.gpus[0]:
            # Transfer from GPU1 to GPU0
            arr1.copy_to_device(arr2)
            np.testing.assert_equal(arr1.copy_to_host(), (hostarr + 2))


if __name__ == '__main__':
    unittest.main()